"""Unit tests for `cora.access._idempotency` (the decorator + hash helper)."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# The bare handler factory is typed via a `# type: ignore` cast at the
# call site (its return type doesn't carry generics), so pyright infers
# Unknown for the wrapped callable's TCommand. Production wrap in
# wire.py uses real-typed handlers; suppress only within these tests.

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from cora.access._idempotency import hash_command, with_idempotency
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import IdempotencyConflictError

_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@dataclass(frozen=True)
class _DummyCommand:
    name: str


_FIXED_RESULT = UUID("01900000-0000-7000-8000-000000001111")


def _make_handler(track_calls: list[int]) -> object:
    """Build a bare handler that records call count and returns _FIXED_RESULT."""

    async def handler(
        command: _DummyCommand,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> UUID:
        _ = (command, principal_id, correlation_id)
        track_calls.append(1)
        return _FIXED_RESULT

    return handler


@pytest.mark.unit
def test_hash_command_is_stable_across_calls() -> None:
    cmd = _DummyCommand(name="Doga")
    assert hash_command(cmd) == hash_command(cmd)


@pytest.mark.unit
def test_hash_command_differs_for_different_field_values() -> None:
    assert hash_command(_DummyCommand(name="A")) != hash_command(_DummyCommand(name="B"))


@pytest.mark.unit
async def test_no_key_skips_cache_entirely() -> None:
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    wrapped = with_idempotency(
        _make_handler(calls),  # type: ignore[arg-type]
        store,
        command_name="DummyCommand",
        serialize_result=str,
        deserialize_result=UUID,
    )

    r1 = await wrapped(
        _DummyCommand(name="A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    r2 = await wrapped(
        _DummyCommand(name="A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert r1 == r2 == _FIXED_RESULT
    assert len(calls) == 2  # both invocations executed
    # Nothing was cached.
    assert await store.get(_PRINCIPAL_ID, "any") is None


@pytest.mark.unit
async def test_first_call_with_key_executes_and_caches() -> None:
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    wrapped = with_idempotency(
        _make_handler(calls),  # type: ignore[arg-type]
        store,
        command_name="DummyCommand",
        serialize_result=str,
        deserialize_result=UUID,
    )

    result = await wrapped(
        _DummyCommand(name="A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key="key-1",
    )

    assert result == _FIXED_RESULT
    assert len(calls) == 1
    cached = await store.get(_PRINCIPAL_ID, "key-1")
    assert cached is not None
    assert cached.command_name == "DummyCommand"
    assert cached.result == str(_FIXED_RESULT)


@pytest.mark.unit
async def test_retry_with_same_key_and_body_returns_cached_without_reexec() -> None:
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    wrapped = with_idempotency(
        _make_handler(calls),  # type: ignore[arg-type]
        store,
        command_name="DummyCommand",
        serialize_result=str,
        deserialize_result=UUID,
    )
    cmd = _DummyCommand(name="A")

    r1 = await wrapped(
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key="key-1",
    )
    r2 = await wrapped(
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key="key-1",
    )

    assert r1 == r2 == _FIXED_RESULT
    assert len(calls) == 1  # only the first call executed; second was cached


@pytest.mark.unit
async def test_retry_with_same_key_but_different_body_raises_conflict() -> None:
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    wrapped = with_idempotency(
        _make_handler(calls),  # type: ignore[arg-type]
        store,
        command_name="DummyCommand",
        serialize_result=str,
        deserialize_result=UUID,
    )

    await wrapped(
        _DummyCommand(name="A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key="key-1",
    )

    with pytest.raises(IdempotencyConflictError) as exc_info:
        await wrapped(
            _DummyCommand(name="B"),  # different body, same key
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            idempotency_key="key-1",
        )
    assert exc_info.value.key == "key-1"
    assert len(calls) == 1  # the conflicting second call was rejected before exec


@pytest.mark.unit
async def test_keys_namespaced_by_principal() -> None:
    """Same key used by different principals doesn't collide."""
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    wrapped = with_idempotency(
        _make_handler(calls),  # type: ignore[arg-type]
        store,
        command_name="DummyCommand",
        serialize_result=str,
        deserialize_result=UUID,
    )
    other_principal = uuid4()

    await wrapped(
        _DummyCommand(name="A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key="shared-key",
    )
    await wrapped(
        _DummyCommand(name="A"),
        principal_id=other_principal,
        correlation_id=_CORRELATION_ID,
        idempotency_key="shared-key",
    )

    # Both executed (different principals = different cache entries).
    assert len(calls) == 2
