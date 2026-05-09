"""Unit tests for `InMemoryIdempotencyStore`."""

from uuid import uuid4

import pytest

from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import CachedResult


def _record(result: object = "abc") -> CachedResult:
    return CachedResult(
        command_hash="deadbeef",
        command_name="RegisterActor",
        result=result,
    )


@pytest.mark.unit
async def test_get_returns_none_for_unknown_key() -> None:
    store = InMemoryIdempotencyStore()
    assert await store.get(uuid4(), "missing") is None


@pytest.mark.unit
async def test_put_then_get_round_trips() -> None:
    store = InMemoryIdempotencyStore()
    principal = uuid4()
    record = _record("01900000-0000-7000-8000-000000000001")
    await store.put(principal, "k1", record)
    assert await store.get(principal, "k1") == record


@pytest.mark.unit
async def test_keys_namespaced_by_principal() -> None:
    store = InMemoryIdempotencyStore()
    p1, p2 = uuid4(), uuid4()
    await store.put(p1, "shared-key", _record("p1-result"))
    await store.put(p2, "shared-key", _record("p2-result"))

    r1 = await store.get(p1, "shared-key")
    r2 = await store.get(p2, "shared-key")
    assert r1 is not None and r1.result == "p1-result"
    assert r2 is not None and r2.result == "p2-result"


@pytest.mark.unit
async def test_put_is_first_writer_wins() -> None:
    """A second put for an existing key must NOT overwrite the first."""
    store = InMemoryIdempotencyStore()
    principal = uuid4()
    await store.put(principal, "k", _record("first"))
    await store.put(principal, "k", _record("second"))

    cached = await store.get(principal, "k")
    assert cached is not None
    assert cached.result == "first"
