"""Shared application dependencies — built once at startup, passed to BC modules.

Each BC's `wire_*(deps)` function pulls the ports it needs from `SharedDeps`
to build its handlers, routes, and MCP tools.

Adapters selected by `Settings.app_env`:
  - `test` -> in-memory adapters (no Postgres needed; used by contract
    tests of API surface that don't care about persistence semantics)
  - anything else -> Postgres-backed adapters over an asyncpg pool

`build_shared_deps` returns the deps and a `teardown` callable so the
lifespan can release pool resources without `SharedDeps` having to expose
its private state.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import asyncpg

from cora.infrastructure.config import Settings
from cora.infrastructure.logging import configure_logging
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    Authorize,
    Clock,
    EventStore,
    IdempotencyStore,
    IdGenerator,
    SystemClock,
    UUIDv7Generator,
)
from cora.infrastructure.postgres.event_store import PostgresEventStore
from cora.infrastructure.postgres.idempotency import PostgresIdempotencyStore
from cora.infrastructure.postgres.pool import create_pool


@dataclass(frozen=True)
class SharedDeps:
    """Process-wide dependencies. Immutable after `build_shared_deps` returns."""

    settings: Settings
    clock: Clock
    id_generator: IdGenerator
    authorize: Authorize
    event_store: EventStore
    idempotency_store: IdempotencyStore


Teardown = Callable[[], Awaitable[None]]


async def build_shared_deps() -> tuple[SharedDeps, Teardown]:
    """Construct shared dependencies. Called once from the FastAPI lifespan."""
    settings = Settings()  # type: ignore[call-arg]  # Pydantic loads from env
    configure_logging(settings.log_level)
    event_store, idempotency_store, teardown = await _build_stores(settings)
    deps = SharedDeps(
        settings=settings,
        clock=SystemClock(),
        id_generator=UUIDv7Generator(),
        authorize=AllowAllAuthorize(),
        event_store=event_store,
        idempotency_store=idempotency_store,
    )
    return deps, teardown


async def _build_stores(
    settings: Settings,
) -> tuple[EventStore, IdempotencyStore, Teardown]:
    if settings.app_env == "test":
        return InMemoryEventStore(), InMemoryIdempotencyStore(), _noop_teardown

    pool = await create_pool(
        settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
    )
    return (
        PostgresEventStore(pool),
        PostgresIdempotencyStore(pool),
        _make_pool_teardown(pool),
    )


async def _noop_teardown() -> None:
    return None


def _make_pool_teardown(pool: asyncpg.Pool) -> Teardown:
    async def teardown() -> None:
        await pool.close()

    return teardown
