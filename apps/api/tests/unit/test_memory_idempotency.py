# pyright: reportPrivateUsage=false

"""Unit tests for `InMemoryIdempotencyStore` (Phase 9a port).

Mirrors `tests/integration/test_postgres_idempotency.py` against the
in-memory adapter. Pins:
  - claim outcomes: Claimed / CachedSuccess / CachedError /
    LockedRecent / HashConflict / stale-lock takeover
  - finalize_success / finalize_error
  - prune deletes only completed rows older than TTL
  - per-principal namespacing
"""

import asyncio
from uuid import uuid4

import pytest

from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import (
    CachedError,
    CachedSuccess,
    Claimed,
    HashConflict,
    LockedRecent,
)


@pytest.mark.unit
async def test_claim_returns_claimed_for_fresh_key() -> None:
    store = InMemoryIdempotencyStore()
    outcome = await store.claim(uuid4(), "k", "h", "X", lock_stale_seconds=60)
    assert isinstance(outcome, Claimed)


@pytest.mark.unit
async def test_claim_returns_cached_success_after_finalize_success() -> None:
    store = InMemoryIdempotencyStore()
    p = uuid4()
    await store.claim(p, "k", "h1", "X", lock_stale_seconds=60)
    await store.finalize_success(p, "k", "result-1")
    outcome = await store.claim(p, "k", "h1", "X", lock_stale_seconds=60)
    assert isinstance(outcome, CachedSuccess)
    assert outcome.result == "result-1"


@pytest.mark.unit
async def test_claim_returns_cached_error_after_finalize_error() -> None:
    store = InMemoryIdempotencyStore()
    p = uuid4()
    await store.claim(p, "k", "h1", "X", lock_stale_seconds=60)
    await store.finalize_error(p, "k", "InvalidActorNameError", "name required")
    outcome = await store.claim(p, "k", "h1", "X", lock_stale_seconds=60)
    assert isinstance(outcome, CachedError)
    assert outcome.error_type == "InvalidActorNameError"
    assert outcome.error_msg == "name required"


@pytest.mark.unit
async def test_claim_returns_locked_recent_on_in_flight_collision() -> None:
    store = InMemoryIdempotencyStore()
    p = uuid4()
    first = await store.claim(p, "k", "h1", "X", lock_stale_seconds=60)
    assert isinstance(first, Claimed)
    second = await store.claim(p, "k", "h1", "X", lock_stale_seconds=60)
    assert isinstance(second, LockedRecent)


@pytest.mark.unit
async def test_claim_takes_over_stale_lock() -> None:
    store = InMemoryIdempotencyStore()
    p = uuid4()
    await store.claim(p, "k", "h1", "X", lock_stale_seconds=60)
    await asyncio.sleep(0.05)
    second = await store.claim(p, "k", "h2", "X", lock_stale_seconds=0)
    assert isinstance(second, Claimed)


@pytest.mark.unit
async def test_claim_returns_hash_conflict_on_different_command() -> None:
    store = InMemoryIdempotencyStore()
    p = uuid4()
    await store.claim(p, "k", "h1", "X", lock_stale_seconds=60)
    await store.finalize_success(p, "k", "result-1")
    outcome = await store.claim(p, "k", "DIFF-HASH", "X", lock_stale_seconds=60)
    assert isinstance(outcome, HashConflict)
    assert outcome.expected_hash == "h1"
    assert outcome.actual_hash == "DIFF-HASH"


@pytest.mark.unit
async def test_keys_namespaced_by_principal() -> None:
    store = InMemoryIdempotencyStore()
    p1, p2 = uuid4(), uuid4()
    await store.claim(p1, "shared", "h1", "X", lock_stale_seconds=60)
    await store.finalize_success(p1, "shared", "p1-result")
    await store.claim(p2, "shared", "h2", "X", lock_stale_seconds=60)
    await store.finalize_success(p2, "shared", "p2-result")

    r1 = await store.claim(p1, "shared", "h1", "X", lock_stale_seconds=60)
    r2 = await store.claim(p2, "shared", "h2", "X", lock_stale_seconds=60)
    assert isinstance(r1, CachedSuccess) and r1.result == "p1-result"
    assert isinstance(r2, CachedSuccess) and r2.result == "p2-result"


@pytest.mark.unit
async def test_prune_returns_zero_when_no_expired_rows() -> None:
    store = InMemoryIdempotencyStore()
    p = uuid4()
    await store.claim(p, "k", "h", "X", lock_stale_seconds=60)
    await store.finalize_success(p, "k", "v")
    deleted = await store.prune(ttl_hours=24)
    assert deleted == 0


@pytest.mark.unit
async def test_prune_skips_in_flight_rows() -> None:
    """In-flight (locked) rows are never pruned even if `created_at`
    is past the TTL window."""
    from datetime import UTC, datetime, timedelta

    from cora.infrastructure.memory.idempotency import _Row

    store = InMemoryIdempotencyStore()
    p = uuid4()
    ancient = datetime.now(tz=UTC) - timedelta(days=365)
    store._records[(p, "k")] = _Row(
        command_hash="h",
        command_name="X",
        created_at=ancient,
        locked_at=ancient,
    )
    deleted = await store.prune(ttl_hours=1)
    assert deleted == 0
