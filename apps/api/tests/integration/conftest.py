"""Integration-test fixtures: per-test Postgres database cloned from
the migrated template.

The session-scoped `postgres_container` and `template_database`
fixtures live in `tests/conftest.py` so the e2e tier can share them.
This module adds the per-test `db_pool`: each test that requests it
gets a fresh database created via `CREATE DATABASE ... TEMPLATE
migrated_db`, which Postgres satisfies via file copy in tens of
milliseconds. The test runs against its own pool; the database is
dropped at teardown.

This is dramatically faster than running migrations per test, and
gives each test full isolation without TRUNCATE bookkeeping.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections.abc import AsyncGenerator
from uuid import uuid4

import asyncpg
import pytest_asyncio
from testcontainers.postgres import PostgresContainer

from cora.infrastructure.postgres.pool import create_pool
from tests._pg import normalize_async_url


@pytest_asyncio.fixture
async def db_pool(
    postgres_container: PostgresContainer,
    template_database: str,
) -> AsyncGenerator[asyncpg.Pool]:
    """Per-test database cloned from the migrated template; dropped at teardown."""
    test_db = f"t_{uuid4().hex[:12]}"
    admin_url = normalize_async_url(postgres_container.get_connection_url(), database="postgres")

    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f'CREATE DATABASE "{test_db}" TEMPLATE "{template_database}"')
    finally:
        await admin.close()

    test_url = normalize_async_url(postgres_container.get_connection_url(), database=test_db)
    pool = await create_pool(test_url, min_size=1, max_size=4)
    try:
        yield pool
    finally:
        await pool.close()
        admin = await asyncpg.connect(admin_url)
        try:
            await admin.execute(f'DROP DATABASE "{test_db}"')
        finally:
            await admin.close()
