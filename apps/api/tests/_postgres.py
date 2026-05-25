"""Shared Postgres URL helpers for integration and e2e test conftests.

Lives at the tests/ root (not in either tier's conftest) so both
`tests/integration/conftest.py::db_pool` and the e2e tier's
`e2e_app` fixture import the same normalization without one tier
reaching into the other's conftest module.
"""

from urllib.parse import urlparse, urlunparse


def normalize_async_url(url: str, *, database: str | None = None) -> str:
    """Drop SQLAlchemy driver prefix; optionally override the database name.

    Testcontainers' `PostgresContainer.get_connection_url()` returns a
    SQLAlchemy-style URL (`postgresql+psycopg2://...`); asyncpg only
    accepts the bare `postgresql://` form. This helper normalizes both
    the scheme and (optionally) the database segment for per-test clones.
    """
    parsed = urlparse(url.replace("postgresql+psycopg2://", "postgresql://"))
    if database is not None:
        parsed = parsed._replace(path=f"/{database}")
    return urlunparse(parsed)
