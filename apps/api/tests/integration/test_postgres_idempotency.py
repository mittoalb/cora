"""Integration tests for `PostgresIdempotencyStore` against real Postgres."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from uuid import uuid4

import asyncpg
import pytest

from cora.infrastructure.ports import CachedResult
from cora.infrastructure.postgres.idempotency import PostgresIdempotencyStore


def _record(result: object = "abc") -> CachedResult:
    return CachedResult(
        command_hash="deadbeefcafebabe",
        command_name="RegisterActor",
        result=result,
    )


@pytest.mark.integration
async def test_get_returns_none_for_unknown_key(db_pool: asyncpg.Pool) -> None:
    store = PostgresIdempotencyStore(db_pool)
    assert await store.get(uuid4(), "missing") is None


@pytest.mark.integration
async def test_put_then_get_round_trips(db_pool: asyncpg.Pool) -> None:
    store = PostgresIdempotencyStore(db_pool)
    principal = uuid4()
    record = _record("01900000-0000-7000-8000-000000000001")
    await store.put(principal, "k1", record)

    cached = await store.get(principal, "k1")
    assert cached == record


@pytest.mark.integration
async def test_keys_namespaced_by_principal(db_pool: asyncpg.Pool) -> None:
    store = PostgresIdempotencyStore(db_pool)
    p1, p2 = uuid4(), uuid4()
    await store.put(p1, "shared-key", _record("p1-result"))
    await store.put(p2, "shared-key", _record("p2-result"))

    r1 = await store.get(p1, "shared-key")
    r2 = await store.get(p2, "shared-key")
    assert r1 is not None and r1.result == "p1-result"
    assert r2 is not None and r2.result == "p2-result"


@pytest.mark.integration
async def test_put_is_first_writer_wins(db_pool: asyncpg.Pool) -> None:
    """ON CONFLICT DO NOTHING: a second put for an existing key is a no-op."""
    store = PostgresIdempotencyStore(db_pool)
    principal = uuid4()
    await store.put(principal, "k", _record("first"))
    await store.put(principal, "k", _record("second"))

    cached = await store.get(principal, "k")
    assert cached is not None
    assert cached.result == "first"


@pytest.mark.integration
async def test_jsonb_round_trips_dict_results(db_pool: asyncpg.Pool) -> None:
    """Cached results are stored as jsonb; nested dicts must survive round-trip."""
    store = PostgresIdempotencyStore(db_pool)
    principal = uuid4()
    body = {"actor_id": "01900000-0000-7000-8000-aaaaaaaaaaaa", "is_active": True}
    await store.put(principal, "k", _record(body))

    cached = await store.get(principal, "k")
    assert cached is not None
    assert cached.result == body
