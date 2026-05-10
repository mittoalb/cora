"""Unit tests for `cora.infrastructure.idempotency` (the decorator + hash helper)."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# The bare handler factory is typed via a `# type: ignore` cast at the
# call site (its return type doesn't carry generics), so pyright infers
# Unknown for the wrapped callable's TCommand. Production wrap in
# wire.py uses real-typed handlers; suppress only within these tests.

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.idempotency import hash_command, with_idempotency
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import IdempotencyConflictError

_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@dataclass(frozen=True)
class _DummyCommand:
    name: str


_FIXED_RESULT = UUID("01900000-0000-7000-8000-000000001111")


def _make_handler(
    track_calls: list[int],
    *,
    capture_causation: list[UUID | None] | None = None,
) -> object:
    """Build a bare handler that records call count and returns _FIXED_RESULT.

    Optionally records each invocation's `causation_id` into
    `capture_causation` so tests can verify the kwarg flows through
    the wrapper without having to inspect a downstream event store.
    """

    async def handler(
        command: _DummyCommand,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> UUID:
        _ = (command, principal_id, correlation_id)
        track_calls.append(1)
        if capture_causation is not None:
            capture_causation.append(causation_id)
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
def test_hash_command_rejects_non_dataclass() -> None:
    """hash_command requires dataclass instances; misuse fails loud."""
    with pytest.raises(TypeError, match="dataclass instance"):
        hash_command({"name": "Doga"})  # type: ignore[arg-type]


@pytest.mark.unit
def test_hash_command_normalizes_frozenset_fields_deterministically() -> None:
    """Pin the cross-process determinism for set-typed command fields.

    `frozenset[str]` iterates in PYTHONHASHSEED-dependent order; without
    normalization, the same logical command produces different hashes
    across worker processes and triggers spurious 422 "Idempotency-Key
    conflict" responses on legitimate retries (real bug surfaced by
    `DefinePolicy`'s `permitted_principals` / `permitted_commands`
    fields in Phase 3c).

    We pin the EXPECTED canonical bytes so a future change to the
    normalization (or a regression that drops it) trips this test
    instead of silently re-introducing the bug under load.
    """
    import hashlib
    import json

    @dataclass(frozen=True)
    class _CmdWithSets:
        cmds: frozenset[str]
        principals: frozenset[UUID]

    p1 = UUID("01900000-0000-7000-8000-000000000a01")
    p2 = UUID("01900000-0000-7000-8000-000000000a02")
    cmd = _CmdWithSets(cmds=frozenset({"Z", "A", "M"}), principals=frozenset({p2, p1}))

    # Normalized form: sets become sorted lists by string form.
    expected_canonical = json.dumps(
        {
            "cmds": ["A", "M", "Z"],
            "principals": [str(p1), str(p2)],
        },
        sort_keys=True,
        default=str,
    )
    expected_hash = hashlib.sha256(expected_canonical.encode()).hexdigest()
    assert hash_command(cmd) == expected_hash


@pytest.mark.unit
def test_hash_command_set_normalization_is_order_independent() -> None:
    """Two frozensets with identical contents but different insertion
    orders must hash the same. Within one Python process, frozenset
    iteration is content-determined and this would pass even without
    normalization; we keep the assertion as a regression guard for
    the normalization path (the cross-process bug is the harder one,
    pinned by the canonical-form test above)."""

    @dataclass(frozen=True)
    class _CmdWithSets:
        cmds: frozenset[str]

    a = _CmdWithSets(cmds=frozenset(["A", "B", "C"]))
    b = _CmdWithSets(cmds=frozenset(["C", "A", "B"]))
    assert hash_command(a) == hash_command(b)


@pytest.mark.unit
async def test_decorator_rejects_idempotency_key_over_255_chars() -> None:
    """Stripe-style 255-char cap protects against abusive clients."""
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    wrapped = with_idempotency(
        _make_handler(calls),  # type: ignore[arg-type]
        store,
        command_name="DummyCommand",
        serialize_result=str,
        deserialize_result=UUID,
    )
    too_long = "x" * 256

    with pytest.raises(ValueError, match="exceeds maximum 255"):
        await wrapped(
            _DummyCommand(name="A"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            idempotency_key=too_long,
        )

    # No store lookup happened, no handler execution.
    assert len(calls) == 0
    assert await store.get(_PRINCIPAL_ID, too_long) is None


@pytest.mark.unit
async def test_decorator_forwards_causation_id_through_to_inner_handler() -> None:
    """`with_idempotency` must pass `causation_id` through to the wrapped
    handler on both code paths (no-key short-circuit AND cached miss).
    Without this, the kwarg added to the bare-handler Protocol would be
    silently dropped at the composition boundary."""
    store = InMemoryIdempotencyStore()
    calls: list[int] = []
    seen_causations: list[UUID | None] = []
    wrapped = with_idempotency(
        _make_handler(calls, capture_causation=seen_causations),  # type: ignore[arg-type]
        store,
        command_name="DummyCommand",
        serialize_result=str,
        deserialize_result=UUID,
    )
    causation = UUID("01900000-0000-7000-8000-0000000000bb")

    # No-key path
    await wrapped(
        _DummyCommand(name="A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    # With-key, cache-miss path (different command body so it's a fresh entry)
    await wrapped(
        _DummyCommand(name="B"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
        idempotency_key="key-causation",
    )

    assert seen_causations == [causation, causation]


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
