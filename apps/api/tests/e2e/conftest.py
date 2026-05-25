"""End-to-end test fixtures: real HTTP + real Postgres + real projections.

The e2e tier is the only place that exercises the full stack at once:
HTTP -> handler -> Postgres event store -> projection worker ->
Postgres projection table -> query handler -> HTTP response. Contract
tests cover the API surface against in-memory adapters; integration
tests cover handlers + adapters against real Postgres but skip the
HTTP edge. e2e closes the gap.

## Wiring

Each `e2e_app` fixture call:
  1. Clones a fresh per-test database from the migrated template
     (see `tests/conftest.py::template_database`).
  2. Monkeypatches `APP_ENV=e2e` (any non-"test" non-"prod" value
     selects the Postgres branch in `cora.infrastructure.deps.build_kernel`)
     and `DATABASE_URL` to the cloned database's URL.
  3. Calls `create_app()` which reads those env vars at construction.
  4. Wraps the app in `asgi_lifespan.LifespanManager` so the lifespan
     fires (`httpx.AsyncClient` doesn't trigger lifespan on its own).
  5. The lifespan's `build_kernel` picks the Postgres adapters,
     constructs the kernel against the test pool, and spawns the
     projection worker against the test database.

The `e2e_client` fixture wraps the app with `httpx.AsyncClient` +
`ASGITransport`; tests call HTTP endpoints through it without a
real socket. The `e2e_drain` fixture exposes a `drain()` callable
that synchronously catches the projection worker up to the latest
event, so reads against projection-backed list endpoints don't race
with the in-process worker.

## Why a fresh app per test

`create_app()` builds a fresh `FastMCP` server each time (per-app
`StreamableHTTPSessionManager`); the documented invariant is that
the same instance's `.run()` cannot be called twice. Per-test
isolation also matters: env-var overrides (`DATABASE_URL`) only
apply to the next `create_app()` call.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import TYPE_CHECKING
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from testcontainers.postgres import PostgresContainer

from cora.infrastructure.projection import drain_projections
from tests._postgres import normalize_async_url

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.projection import ProjectionRegistry


@pytest_asyncio.fixture
async def e2e_app(
    postgres_container: PostgresContainer,
    template_database: str,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[FastAPI]:
    """FastAPI app whose lifespan picks up a per-test cloned database.

    Yields an app with `app.state.deps` (Kernel) and `app.state.projections`
    (ProjectionRegistry) populated by the lifespan. Drops the per-test
    database at teardown.
    """
    test_db = f"e2e_{uuid4().hex[:12]}"
    admin_url = normalize_async_url(
        postgres_container.get_connection_url(),
        database="postgres",
    )

    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(
            f'CREATE DATABASE "{test_db}" TEMPLATE "{template_database}"',
        )
    finally:
        await admin.close()

    test_url = normalize_async_url(
        postgres_container.get_connection_url(),
        database=test_db,
    )

    # Override env so create_app's Settings() picks these. Setenv with
    # monkeypatch auto-restores at fixture teardown.
    monkeypatch.setenv("APP_ENV", "e2e")
    monkeypatch.setenv("DATABASE_URL", test_url)
    # Use poll-only wakeup for e2e; the LISTEN/NOTIFY long-lived
    # connection complicates teardown cleanly across many short tests.
    # Polling is fine for tests because `e2e_drain` is the deterministic
    # mechanism — the worker's wakeup timing is irrelevant.
    monkeypatch.setenv("PROJECTION_USE_LISTEN_NOTIFY", "false")
    # Tighten the poll interval so worker overhead during the test
    # window stays low (default 5s would mean each test waits up to 5s
    # for the worker to spin once). 0.1s is the floor.
    monkeypatch.setenv("PROJECTION_POLL_INTERVAL_SECONDS", "0.1")

    # Imported here (after env vars are set) so any module-level Settings
    # reads inside cora.api.main pick up the override. create_app() also
    # reads Settings inside, which is the load-bearing call.
    from cora.api.main import create_app

    app = create_app()
    try:
        # shutdown_timeout=30 (vs asgi-lifespan default of 5): the MCP
        # `StreamableHTTPSessionManager` shutdown reliably takes ~5s
        # before logging "session manager shutting down", which trips
        # the default deadline and surfaces a TaskGroup TimeoutError
        # in test teardown even though every assertion already passed.
        async with LifespanManager(app, shutdown_timeout=30):
            yield app
    finally:
        admin = await asyncpg.connect(admin_url)
        try:
            await admin.execute(f'DROP DATABASE "{test_db}"')
        finally:
            await admin.close()


@pytest_asyncio.fixture
async def e2e_client(e2e_app: FastAPI) -> AsyncGenerator[AsyncClient]:
    """Async HTTP client backed by ASGITransport (no real socket)."""
    transport = ASGITransport(app=e2e_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def e2e_drain(e2e_app: FastAPI) -> Callable[[], Awaitable[None]]:
    """Synchronously advance every projection to the latest event.

    The projection worker is also running in the background lifespan;
    drain just guarantees the bookmark caught up before a test reads
    a projection-backed endpoint. If the worker already advanced past,
    drain returns immediately.

    Use 5s deadline (the `drain_projections` default); raise the value
    via the `deadline_seconds` kwarg if a future test produces enough
    events to need it.
    """

    async def drain(deadline_seconds: float = 5.0) -> None:
        deps: Kernel = e2e_app.state.deps
        registry: ProjectionRegistry = e2e_app.state.projections
        if deps.pool is None:
            msg = "e2e_drain called against an in-memory kernel; check APP_ENV"
            raise RuntimeError(msg)
        await drain_projections(deps.pool, registry, deadline_seconds=deadline_seconds)

    return drain
