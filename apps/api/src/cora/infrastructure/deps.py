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

## Single-Kernel-construction-site invariant

`Kernel(...)` is constructed in exactly two places: `make_postgres_kernel`
and `make_inmemory_kernel` below. Production's `build_kernel` calls
the appropriate primitive with `SystemClock` / `UUIDv7Generator` /
env-loaded `Settings`; tests call the same primitives via thin
wrappers in `tests/unit/_helpers.py` and `tests/integration/_helpers.py`
that supply `FrozenClock` / `FixedIdGenerator` / test `Settings`.

The architecture fitness function
`tests/architecture/test_kernel_construction_single_site.py` enforces
this invariant: any direct `Kernel(...)` call outside this module
fails the build. Adding a required `Kernel` field then needs to land
in exactly two function bodies (the two primitives) instead of every
test file individually.
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


def make_postgres_kernel(
    pool: asyncpg.Pool,
    *,
    settings: Settings,
    clock: Clock,
    id_generator: IdGenerator,
    authorize: Authorize,
    event_store: EventStore | None = None,
    idempotency_store: IdempotencyStore | None = None,
) -> Kernel:
    """Postgres-backed Kernel primitive.

    Single construction site for `Kernel(...)` with a Postgres pool.
    Production's `build_kernel` postgres branch calls this with
    `SystemClock` + `UUIDv7Generator` + env-loaded `Settings` + the
    `authorize` instance built around `event_store`. Integration tests
    call it via the `tests.integration._helpers.build_postgres_deps`
    wrapper, which supplies `FrozenClock` + `FixedIdGenerator` + test
    `Settings`.

    `event_store` / `idempotency_store` default to fresh
    `PostgresEventStore(pool)` / `PostgresIdempotencyStore(pool)` for
    test convenience. Production passes the prebuilt instances so
    they're shared with the authorize_factory (chicken-and-egg:
    `authorize` needs `event_store` before the Kernel is constructed).
    """
    return Kernel(
        settings=settings,
        clock=clock,
        id_generator=id_generator,
        authorize=authorize,
        event_store=event_store if event_store is not None else PostgresEventStore(pool),
        idempotency_store=(
            idempotency_store if idempotency_store is not None else PostgresIdempotencyStore(pool)
        ),
        pool=pool,
    )


def make_inmemory_kernel(
    *,
    settings: Settings,
    clock: Clock,
    id_generator: IdGenerator,
    authorize: Authorize,
    event_store: EventStore | None = None,
    idempotency_store: IdempotencyStore | None = None,
) -> Kernel:
    """In-memory Kernel primitive.

    Single construction site for `Kernel(...)` with no Postgres pool.
    Production's `build_kernel` `app_env=test` branch calls this for
    contract tests of the API surface. Unit tests call it via the
    `tests.unit._helpers.build_deps` wrapper.

    Two unit-test files allowlisted in the architecture fitness
    function (`test_idempotency_pruner.py` for a pool-presence
    sentinel; `test_list_actors_handler.py` predates the helper)
    construct `Kernel(...)` directly and don't go through this
    primitive.
    """
    return Kernel(
        settings=settings,
        clock=clock,
        id_generator=id_generator,
        authorize=authorize,
        event_store=event_store if event_store is not None else InMemoryEventStore(),
        idempotency_store=(
            idempotency_store if idempotency_store is not None else InMemoryIdempotencyStore()
        ),
        pool=None,
    )


async def build_kernel(*, authorize_factory: AuthorizeFactory) -> tuple[Kernel, Teardown]:
    """Construct the kernel. Called once from the FastAPI lifespan."""
    settings = Settings()  # type: ignore[call-arg]  # Pydantic loads from env
    configure_logging(settings.log_level)
    clock = SystemClock()
    id_generator = UUIDv7Generator()

    if settings.app_env == "test":
        event_store: EventStore = InMemoryEventStore()
        idempotency_store: IdempotencyStore = InMemoryIdempotencyStore()
        authorize = authorize_factory(
            settings,
            event_store,
            pool=None,
            clock=clock,
            id_generator=id_generator,
        )
        kernel = make_inmemory_kernel(
            settings=settings,
            clock=clock,
            id_generator=id_generator,
            authorize=authorize,
            event_store=event_store,
            idempotency_store=idempotency_store,
        )
        return kernel, _noop_teardown

    pool = await create_pool(
        settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
    )
    pg_event_store: EventStore = PostgresEventStore(pool)
    pg_idempotency_store: IdempotencyStore = PostgresIdempotencyStore(pool)
    authorize = authorize_factory(
        settings,
        pg_event_store,
        pool=pool,
        clock=clock,
        id_generator=id_generator,
    )
    kernel = make_postgres_kernel(
        pool,
        settings=settings,
        clock=clock,
        id_generator=id_generator,
        authorize=authorize,
        event_store=pg_event_store,
        idempotency_store=pg_idempotency_store,
    )
    return kernel, _make_pool_teardown(pool)


async def _noop_teardown() -> None:
    return None


def _make_pool_teardown(pool: asyncpg.Pool) -> Teardown:
    async def teardown() -> None:
        await pool.close()

    return teardown


__all__ = [
    "AuthorizeFactory",
    "build_kernel",
    "make_inmemory_kernel",
    "make_postgres_kernel",
]
