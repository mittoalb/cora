"""Integration tests for `PostgresIdempotencyStore` against real Postgres.

Pins the new claim/finalize/prune surface end-to-end:
  - claim returns Claimed for a fresh key
  - claim returns CachedSuccess after finalize_success
  - claim returns CachedError after finalize_error
  - claim returns LockedRecent on a fresh in-flight lock
  - claim returns Claimed on stale-lock takeover
  - claim returns HashConflict for same key + different command_hash
  - prune deletes only completed rows older than the TTL window
  - keys are namespaced per-principal AND per-surface
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncio
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.adapters.postgres_idempotency_store import PostgresIdempotencyStore
from cora.infrastructure.ports import (
    CachedError,
    CachedSuccess,
    Claimed,
    HashConflict,
    LockedRecent,
)

_SURFACE = UUID("00000000-0000-0000-0000-000000000020")


@pytest.mark.integration
async def test_claim_returns_claimed_for_fresh_key(db_pool: asyncpg.Pool) -> None:
    store = PostgresIdempotencyStore(db_pool)
    outcome = await store.claim(
        uuid4(), "fresh-key", _SURFACE, "hash1", "RegisterActor", lock_stale_seconds=60
    )
    assert isinstance(outcome, Claimed)


@pytest.mark.integration
async def test_claim_returns_cached_success_after_finalize_success(
    db_pool: asyncpg.Pool,
) -> None:
    store = PostgresIdempotencyStore(db_pool)
    principal = uuid4()
    await store.claim(principal, "k", _SURFACE, "hash1", "RegisterActor", lock_stale_seconds=60)
    await store.finalize_success(principal, "k", _SURFACE, "result-1")

    outcome = await store.claim(
        principal, "k", _SURFACE, "hash1", "RegisterActor", lock_stale_seconds=60
    )
    assert isinstance(outcome, CachedSuccess)
    assert outcome.result == "result-1"
    assert outcome.command_hash == "hash1"


@pytest.mark.integration
async def test_claim_returns_cached_error_after_finalize_error(
    db_pool: asyncpg.Pool,
) -> None:
    store = PostgresIdempotencyStore(db_pool)
    principal = uuid4()
    await store.claim(principal, "k", _SURFACE, "hash1", "RegisterActor", lock_stale_seconds=60)
    await store.finalize_error(
        principal, "k", _SURFACE, "InvalidActorNameError", "name must be 1-200 chars"
    )

    outcome = await store.claim(
        principal, "k", _SURFACE, "hash1", "RegisterActor", lock_stale_seconds=60
    )
    assert isinstance(outcome, CachedError)
    assert outcome.error_type == "InvalidActorNameError"
    assert outcome.error_msg == "name must be 1-200 chars"


@pytest.mark.integration
async def test_claim_returns_locked_recent_on_in_flight_collision(
    db_pool: asyncpg.Pool,
) -> None:
    store = PostgresIdempotencyStore(db_pool)
    principal = uuid4()
    first = await store.claim(
        principal, "k", _SURFACE, "hash1", "RegisterActor", lock_stale_seconds=60
    )
    assert isinstance(first, Claimed)

    second = await store.claim(
        principal, "k", _SURFACE, "hash1", "RegisterActor", lock_stale_seconds=60
    )
    assert isinstance(second, LockedRecent)


@pytest.mark.integration
async def test_claim_takes_over_stale_lock(db_pool: asyncpg.Pool) -> None:
    """If the lock is older than `lock_stale_seconds`, the next claim
    atomically takes it over (worker-crash recovery)."""
    store = PostgresIdempotencyStore(db_pool)
    principal = uuid4()
    await store.claim(principal, "k", _SURFACE, "hash1", "RegisterActor", lock_stale_seconds=60)
    await asyncio.sleep(0.05)
    second = await store.claim(
        principal, "k", _SURFACE, "hash2", "RegisterActor", lock_stale_seconds=0
    )
    assert isinstance(second, Claimed)


@pytest.mark.integration
async def test_claim_returns_hash_conflict_on_different_command(
    db_pool: asyncpg.Pool,
) -> None:
    """Same key reused with a DIFFERENT command body. Client bug -> 422."""
    store = PostgresIdempotencyStore(db_pool)
    principal = uuid4()
    await store.claim(principal, "k", _SURFACE, "hash1", "RegisterActor", lock_stale_seconds=60)
    await store.finalize_success(principal, "k", _SURFACE, "result-1")

    outcome = await store.claim(
        principal, "k", _SURFACE, "DIFFERENT-HASH", "RegisterActor", lock_stale_seconds=60
    )
    assert isinstance(outcome, HashConflict)
    assert outcome.expected_hash == "hash1"
    assert outcome.actual_hash == "DIFFERENT-HASH"


@pytest.mark.integration
async def test_keys_namespaced_by_principal(db_pool: asyncpg.Pool) -> None:
    store = PostgresIdempotencyStore(db_pool)
    p1, p2 = uuid4(), uuid4()
    await store.claim(p1, "shared-key", _SURFACE, "hash1", "X", lock_stale_seconds=60)
    await store.finalize_success(p1, "shared-key", _SURFACE, "p1-result")
    await store.claim(p2, "shared-key", _SURFACE, "hash2", "X", lock_stale_seconds=60)
    await store.finalize_success(p2, "shared-key", _SURFACE, "p2-result")

    r1 = await store.claim(p1, "shared-key", _SURFACE, "hash1", "X", lock_stale_seconds=60)
    r2 = await store.claim(p2, "shared-key", _SURFACE, "hash2", "X", lock_stale_seconds=60)
    assert isinstance(r1, CachedSuccess) and r1.result == "p1-result"
    assert isinstance(r2, CachedSuccess) and r2.result == "p2-result"


@pytest.mark.integration
async def test_keys_namespaced_by_surface(db_pool: asyncpg.Pool) -> None:
    """Same (principal, key, command_hash) but DIFFERENT surface yields
     independent cache slots. Each Surface's policy authorizes independently
    ."""
    store = PostgresIdempotencyStore(db_pool)
    principal = uuid4()
    surf_http = UUID("00000000-0000-0000-0000-000000000020")
    surf_mcp = UUID("00000000-0000-0000-0000-000000000022")

    await store.claim(principal, "shared", surf_http, "hash1", "X", lock_stale_seconds=60)
    await store.finalize_success(principal, "shared", surf_http, "http-result")
    await store.claim(principal, "shared", surf_mcp, "hash1", "X", lock_stale_seconds=60)
    await store.finalize_success(principal, "shared", surf_mcp, "mcp-result")

    r_http = await store.claim(principal, "shared", surf_http, "hash1", "X", lock_stale_seconds=60)
    r_mcp = await store.claim(principal, "shared", surf_mcp, "hash1", "X", lock_stale_seconds=60)
    assert isinstance(r_http, CachedSuccess) and r_http.result == "http-result"
    assert isinstance(r_mcp, CachedSuccess) and r_mcp.result == "mcp-result"


@pytest.mark.integration
async def test_jsonb_round_trips_dict_results(db_pool: asyncpg.Pool) -> None:
    """Cached results are stored as jsonb; nested dicts must survive round-trip."""
    store = PostgresIdempotencyStore(db_pool)
    principal = uuid4()
    body = {"actor_id": "01900000-0000-7000-8000-aaaaaaaaaaaa", "is_active": True}
    await store.claim(principal, "k", _SURFACE, "hash1", "X", lock_stale_seconds=60)
    await store.finalize_success(principal, "k", _SURFACE, body)

    outcome = await store.claim(principal, "k", _SURFACE, "hash1", "X", lock_stale_seconds=60)
    assert isinstance(outcome, CachedSuccess)
    assert outcome.result == body


@pytest.mark.integration
async def test_prune_deletes_only_old_completed_rows(db_pool: asyncpg.Pool) -> None:
    """Rows older than `ttl_hours` AND completed (locked_at IS NULL)
    are deleted; in-flight rows survive (locked_at predicate)."""
    store = PostgresIdempotencyStore(db_pool)
    principal = uuid4()
    await store.claim(principal, "old-completed", _SURFACE, "h", "X", lock_stale_seconds=60)
    await store.finalize_success(principal, "old-completed", _SURFACE, "x")
    await store.claim(principal, "new-completed", _SURFACE, "h", "X", lock_stale_seconds=60)
    await store.finalize_success(principal, "new-completed", _SURFACE, "x")
    await store.claim(principal, "old-locked", _SURFACE, "h", "X", lock_stale_seconds=60)

    # Backdate created_at on the two "old" rows (year ago).
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE idempotency_keys SET created_at = now() - interval '365 days' "
            "WHERE principal_id = $1 AND key IN ('old-completed', 'old-locked')",
            principal,
        )

    deleted = await store.prune(ttl_hours=1)
    assert deleted == 1  # only old-completed (in-flight excluded by SQL)

    # new-completed survives — confirmed via cache hit.
    new_outcome = await store.claim(
        principal, "new-completed", _SURFACE, "h", "X", lock_stale_seconds=60
    )
    assert isinstance(new_outcome, CachedSuccess)

    # old-locked also survives (locked_at predicate excluded it from prune).
    # Subsequent claim sees LockedRecent because locked_at itself is recent
    # (only created_at was backdated; locked_at was set by the original
    # claim a few ms ago).
    old_locked_outcome = await store.claim(
        principal, "old-locked", _SURFACE, "h", "X", lock_stale_seconds=60
    )
    assert isinstance(old_locked_outcome, LockedRecent)
