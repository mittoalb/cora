"""Kernel-construction orchestration.

`build_kernel` builds the process-wide `Kernel` from `Settings`,
called once from the FastAPI lifespan. The authorize-port factory
is INJECTED via the `authorize_factory` callable so this module
has zero BC imports (Phase-8d hardening: the prior version lazy-
imported `cora.trust` for `_build_authorize`, which tach correctly
flagged as a layer violation even though Python tolerated it).

Composition root (`cora.api.main`) injects
`cora.trust.authorize_factory.build_authorize`; tests inject any
`Authorize` factory they want (typically
`lambda *a, **kw: AllowAllAuthorize()`).

Adapter selection is driven by `Settings.app_env`:
  - `test` -> in-memory adapters (no Postgres needed; used by
    contract tests of API surface that don't care about
    persistence semantics)
  - anything else -> Postgres-backed adapters over an asyncpg pool

`build_kernel` returns the kernel and a `teardown` callable so the
lifespan can release pool resources without `Kernel` having to
expose its private state.
"""

from typing import Protocol

import asyncpg

from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel, Teardown
from cora.infrastructure.logging import configure_logging
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import (
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


class AuthorizeFactory(Protocol):
    """Builds the production Authorize port for the Kernel.

    Injected by the composition root so this module stays BC-free.
    Production wires `cora.trust.authorize_factory.build_authorize`;
    tests inject lambda-shaped factories.
    """

    def __call__(
        self,
        settings: Settings,
        event_store: EventStore,
        *,
        pool: asyncpg.Pool | None,
        clock: Clock,
        id_generator: IdGenerator,
    ) -> Authorize: ...


async def build_kernel(*, authorize_factory: AuthorizeFactory) -> tuple[Kernel, Teardown]:
    """Construct the kernel. Called once from the FastAPI lifespan."""
    settings = Settings()  # type: ignore[call-arg]  # Pydantic loads from env
    configure_logging(settings.log_level)
    pool, event_store, idempotency_store, teardown = await _build_stores(settings)
    clock = SystemClock()
    id_generator = UUIDv7Generator()
    kernel = Kernel(
        settings=settings,
        clock=clock,
        id_generator=id_generator,
        authorize=authorize_factory(
            settings,
            event_store,
            pool=pool,
            clock=clock,
            id_generator=id_generator,
        ),
        event_store=event_store,
        idempotency_store=idempotency_store,
        pool=pool,
    )
    return kernel, teardown


async def _build_stores(
    settings: Settings,
) -> tuple[asyncpg.Pool | None, EventStore, IdempotencyStore, Teardown]:
    if settings.app_env == "test":
        return (
            None,
            InMemoryEventStore(),
            InMemoryIdempotencyStore(),
            _noop_teardown,
        )

    pool = await create_pool(
        settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
    )
    return (
        pool,
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


__all__ = [
    "AuthorizeFactory",
    "build_kernel",
]
