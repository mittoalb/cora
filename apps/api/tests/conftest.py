"""Pytest configuration and shared fixtures.

`APP_ENV=test` is set before any test imports so unit + contract tests
that build a FastAPI app via `create_app()` get the in-memory adapters
by default. Integration and e2e tests override this on a per-test
basis (integration: tests build their own Kernel against `db_pool`;
e2e: the `e2e_app` fixture monkeypatches `APP_ENV` + `DATABASE_URL`
so the lifespan picks the testcontainers Postgres branch).

## Session-scoped Postgres container

`postgres_container` and `template_database` live here (not in the
integration tier's conftest) so the integration `db_pool` fixture and
the e2e `e2e_app` fixture share one container per test session. The
template-DB clone strategy: migrations apply once into the container's
default DB; each per-test database is created via `CREATE DATABASE
... TEMPLATE migrated_db`, which Postgres satisfies via file copy in
tens of milliseconds.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import os
from collections.abc import Generator
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer

from tests._pg import normalize_async_url

os.environ.setdefault("APP_ENV", "test")

# Repo-root/infra/atlas/migrations relative to this conftest.
_MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "infra" / "atlas" / "migrations"


def _read_migration_statements() -> list[str]:
    """Read migration .sql files in order. Each file is executed as one batch."""
    files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    return [f.read_text() for f in files]


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer]:
    """One Postgres container per test session, shared by integration + e2e tiers."""
    container = PostgresContainer("pgvector/pgvector:pg18", driver=None)
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest_asyncio.fixture(scope="session")
async def template_database(postgres_container: PostgresContainer) -> str:
    """Apply migrations once; the resulting DB becomes the template for clones."""
    base_url = normalize_async_url(postgres_container.get_connection_url())
    template_name = urlparse(base_url).path.lstrip("/")

    conn = await asyncpg.connect(base_url)
    try:
        for sql in _read_migration_statements():
            await conn.execute(sql)
    finally:
        await conn.close()

    return template_name
