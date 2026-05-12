"""Integration-test fixtures: testcontainers Postgres + per-test template-DB clone.

Strategy
--------
A single Postgres container is spun up for the whole test session. All
schema migrations are applied once into the container's default database;
that database is then used as a template. Each test that requests
`db_pool` gets a fresh database created via
`CREATE DATABASE ... TEMPLATE migrated_db`, which Postgres satisfies via
file copy in tens of milliseconds. The test runs against its own pool;
the database is dropped at teardown.

This is dramatically faster than running migrations per test, and gives
each test full isolation without TRUNCATE bookkeeping.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer

from cora.infrastructure.postgres.pool import create_pool

# Repo-root/infra/atlas/migrations relative to this conftest.
_MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "infra" / "atlas" / "migrations"


def _normalize_async_url(url: str, *, database: str | None = None) -> str:
    """Drop SQLAlchemy driver prefix; optionally override the database name."""
    parsed = urlparse(url.replace("postgresql+psycopg2://", "postgresql://"))
    if database is not None:
        parsed = parsed._replace(path=f"/{database}")
    return urlunparse(parsed)


def _read_migration_statements() -> list[str]:
    """Read migration .sql files in order. Each file is executed as one batch."""
    files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    return [f.read_text() for f in files]


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer]:
    """One Postgres container per test session."""
    container = PostgresContainer("pgvector/pgvector:pg18", driver=None)
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest_asyncio.fixture(scope="session")
async def template_database(postgres_container: PostgresContainer) -> str:
    """Apply migrations once; the resulting DB becomes the template for clones."""
    base_url = _normalize_async_url(postgres_container.get_connection_url())
    template_name = urlparse(base_url).path.lstrip("/")

    conn = await asyncpg.connect(base_url)
    try:
        for sql in _read_migration_statements():
            await conn.execute(sql)
    finally:
        await conn.close()

    return template_name


@pytest_asyncio.fixture
async def db_pool(
    postgres_container: PostgresContainer,
    template_database: str,
) -> AsyncGenerator[asyncpg.Pool]:
    """Per-test database cloned from the migrated template; dropped at teardown."""
    test_db = f"t_{uuid4().hex[:12]}"
    admin_url = _normalize_async_url(postgres_container.get_connection_url(), database="postgres")

    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f'CREATE DATABASE "{test_db}" TEMPLATE "{template_database}"')
    finally:
        await admin.close()

    test_url = _normalize_async_url(postgres_container.get_connection_url(), database=test_db)
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
