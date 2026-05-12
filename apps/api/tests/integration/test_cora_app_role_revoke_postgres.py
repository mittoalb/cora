"""Integration test: cora_app role cannot UPDATE / DELETE append-only tables.

Phase 8d foundation hardening. The migration
`20260512230000_init_role_cora_app.sql` creates a `cora_app` database
role and grants SELECT + INSERT only on `events` and every `entries_*`
table, plus a belt-and-suspenders REVOKE on UPDATE / DELETE / TRUNCATE.
This test proves the REVOKE actually denies the operation when the
app pool runs as `cora_app` (not as the database owner the rest of the
suite uses).

What this test guards against:

  - Future migrations granting ALL on append-only tables by mistake
  - Code paths that issue UPDATE on `events` slipping through code
    review (Postgres now refuses them at the role boundary)
  - The classic event-sourcing failure mode where "events are
    immutable" is documented but not enforced

The fixtures in `conftest.py` connect as the testcontainers
superuser so the rest of the suite can TRUNCATE between tests.
This test reaches around that and opens a separate `cora_app`
pool against the same per-test database to verify the role
boundary holds.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections.abc import AsyncGenerator
from urllib.parse import urlparse, urlunparse
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer


def _cora_app_url(container: PostgresContainer, *, database: str) -> str:
    """Build the cora_app connection URL for the given test database.

    The migration-defined password is `cora_app` (greenfield local-dev
    convention; production rotates via secret store). The host / port
    come from the testcontainers container; the database is the
    per-test clone.
    """
    base = container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
    parsed = urlparse(base)
    netloc = f"cora_app:cora_app@{parsed.hostname}:{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc, path=f"/{database}"))


@pytest_asyncio.fixture
async def cora_app_pool(
    postgres_container: PostgresContainer,
    db_pool: asyncpg.Pool,
) -> AsyncGenerator[asyncpg.Pool]:
    """Pool connected as `cora_app` to the same per-test database
    that `db_pool` (admin) is connected to.

    Reads the per-test database name off `db_pool` so both fixtures
    target the same database; the schema, sequences, and any seeded
    rows admin inserts are visible.
    """
    async with db_pool.acquire() as conn:
        db_name = await conn.fetchval("SELECT current_database()")
    assert isinstance(db_name, str)

    pool = await asyncpg.create_pool(
        _cora_app_url(postgres_container, database=db_name),
        min_size=1,
        max_size=1,
    )
    assert pool is not None
    try:
        yield pool
    finally:
        await pool.close()


async def _seed_one_event(admin_pool: asyncpg.Pool, *, stream_id: UUID) -> None:
    """Insert one minimal event row via the admin pool for the cora_app
    pool to attempt UPDATE / DELETE against."""
    async with admin_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (
                event_id, stream_type, stream_id, version, event_type,
                payload, correlation_id, occurred_at
            ) VALUES (
                $3, 'TestStream', $1, 1, 'TestEvent',
                '{}'::jsonb, $2, now()
            )
            """,
            stream_id,
            uuid4(),
            uuid4(),
        )


@pytest.mark.integration
async def test_cora_app_can_select_and_insert_events(
    cora_app_pool: asyncpg.Pool,
) -> None:
    """Sanity: cora_app has the grants it needs for normal operation."""
    stream_id = uuid4()
    correlation_id = uuid4()
    event_id = uuid4()

    async with cora_app_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (
                event_id, stream_type, stream_id, version, event_type,
                payload, correlation_id, occurred_at
            ) VALUES (
                $3, 'TestStream', $1, 1, 'TestEvent',
                '{}'::jsonb, $2, now()
            )
            """,
            stream_id,
            correlation_id,
            event_id,
        )
        rows = await conn.fetch(
            "SELECT version FROM events WHERE stream_id = $1",
            stream_id,
        )
    assert len(rows) == 1


@pytest.mark.integration
async def test_cora_app_cannot_update_events(
    db_pool: asyncpg.Pool,
    cora_app_pool: asyncpg.Pool,
) -> None:
    """REVOKE UPDATE: cora_app gets InsufficientPrivilegeError."""
    stream_id = uuid4()
    await _seed_one_event(db_pool, stream_id=stream_id)

    async with cora_app_pool.acquire() as conn:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(
                "UPDATE events SET event_type = 'TamperedEvent' WHERE stream_id = $1",
                stream_id,
            )


@pytest.mark.integration
async def test_cora_app_cannot_delete_events(
    db_pool: asyncpg.Pool,
    cora_app_pool: asyncpg.Pool,
) -> None:
    """REVOKE DELETE: cora_app gets InsufficientPrivilegeError."""
    stream_id = uuid4()
    await _seed_one_event(db_pool, stream_id=stream_id)

    async with cora_app_pool.acquire() as conn:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(
                "DELETE FROM events WHERE stream_id = $1",
                stream_id,
            )


@pytest.mark.integration
async def test_cora_app_cannot_truncate_events(
    cora_app_pool: asyncpg.Pool,
) -> None:
    """REVOKE TRUNCATE: cora_app gets InsufficientPrivilegeError."""
    async with cora_app_pool.acquire() as conn:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute("TRUNCATE events")


@pytest.mark.integration
@pytest.mark.parametrize(
    "table",
    ["entries_conduit_traversals", "entries_decision_reasonings"],
)
async def test_cora_app_cannot_update_or_delete_entries_tables(
    cora_app_pool: asyncpg.Pool,
    table: str,
) -> None:
    """REVOKE UPDATE / DELETE applies uniformly to every entries_*
    table. New entries_* tables added in future migrations will be
    caught by the architecture-fitness test that scans migration files
    for matching REVOKE statements."""
    async with cora_app_pool.acquire() as conn:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(f"UPDATE {table} SET event_id = $1", uuid4())
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(f"DELETE FROM {table}")


@pytest.mark.integration
async def test_cora_app_can_mutate_idempotency_keys(
    cora_app_pool: asyncpg.Pool,
) -> None:
    """idempotency_keys is a mutable cache; UPDATE / DELETE allowed."""
    principal = uuid4()
    key = "test-key"
    async with cora_app_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO idempotency_keys (
                principal_id, key, command_hash, command_name, result
            ) VALUES ($1, $2, 'h', 'TestCmd', '{}'::jsonb)
            """,
            principal,
            key,
        )
        await conn.execute(
            "UPDATE idempotency_keys SET result = $3 WHERE principal_id = $1 AND key = $2",
            principal,
            key,
            '{"updated": true}',
        )
        await conn.execute(
            "DELETE FROM idempotency_keys WHERE principal_id = $1 AND key = $2",
            principal,
            key,
        )
