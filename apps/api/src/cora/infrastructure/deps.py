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

## SharedDeps shape and BC-specific stores

`SharedDeps` carries the cross-BC primitives (settings, clock,
id_generator, authorize, event_store, idempotency_store) plus the
asyncpg `pool` (None for `app_env=test`). BC-specific observation
stores (e.g., the Trust BC's `TraversalStore`) are constructed by
each BC's wire function using the pool, and live BC-internal —
they are NOT promoted to SharedDeps fields. This keeps the
cross-BC dependency container clean as more BCs adopt the channel
+ observation pattern.

## Phase 6f-5a: TrustAuthorize observation wiring

TrustAuthorize is the production Authorize-port adapter. When
constructed (only when `Settings.trust_policy_id` is set), it
receives the Trust BC's `TraversalStore` so it can emit one
`ConduitTraversal` row per Allow / Deny decision. The TraversalStore
is built locally inside `_build_authorize` rather than passing
through SharedDeps. The AllowAllAuthorize fallback skips emission
entirely.
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
    """Process-wide dependencies. Immutable after `build_shared_deps` returns.

    `pool` is the asyncpg connection pool (None when `app_env=test`).
    BCs that need additional Postgres-backed adapters (observation
    stores, projections, etc.) construct them in their own
    `wire_<bc>(deps)` from this pool, keeping BC-specific stores out
    of SharedDeps.
    """

    settings: Settings
    clock: Clock
    id_generator: IdGenerator
    authorize: Authorize
    event_store: EventStore
    idempotency_store: IdempotencyStore
    pool: asyncpg.Pool | None = None


Teardown = Callable[[], Awaitable[None]]


async def build_shared_deps() -> tuple[SharedDeps, Teardown]:
    """Construct shared dependencies. Called once from the FastAPI lifespan."""
    settings = Settings()  # type: ignore[call-arg]  # Pydantic loads from env
    configure_logging(settings.log_level)
    pool, event_store, idempotency_store, teardown = await _build_stores(settings)
    clock = SystemClock()
    id_generator = UUIDv7Generator()
    deps = SharedDeps(
        settings=settings,
        clock=clock,
        id_generator=id_generator,
        authorize=_build_authorize(
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
    return deps, teardown


def _build_authorize(
    settings: Settings,
    event_store: EventStore,
    *,
    pool: asyncpg.Pool | None,
    clock: Clock,
    id_generator: IdGenerator,
) -> Authorize:
    """Choose the Authorize adapter based on Settings.

    `trust_policy_id` unset (None) → `AllowAllAuthorize` (Phase 1
    permissive default; matches dev/test). Set → `TrustAuthorize` gates
    every command through that single Policy aggregate. See
    `cora/trust/authorize.py` for the bootstrap workflow when first
    enabling real auth in a deployment.

    `TrustAuthorize` (and its `TraversalStore`) are imported lazily
    because `cora.trust.__init__` transitively imports `SharedDeps`
    from this module (via `cora.trust.wire` → handlers); a top-level
    import here would trigger a partially-initialized-module circular
    import. Splitting `SharedDeps` into a separate module would also
    fix it but is a bigger refactor; the lazy imports are local to
    this function.

    Phase 6f-5a: when `TrustAuthorize` is wired, the TraversalStore is
    constructed inline (Postgres if pool is set, in-memory otherwise)
    and passed in alongside clock + id_generator so the adapter emits
    per-decision ConduitTraversal observations. AllowAllAuthorize stays
    bare (no observations from the permissive default).
    """
    if settings.trust_policy_id is None:
        return AllowAllAuthorize()

    from cora.trust.aggregates.conduit.observations import (
        InMemoryTraversalStore,
        PostgresTraversalStore,
        TraversalStore,
    )
    from cora.trust.authorize import TrustAuthorize

    traversals_store: TraversalStore = (
        PostgresTraversalStore(pool) if pool is not None else InMemoryTraversalStore()
    )
    return TrustAuthorize(
        event_store,
        policy_id=settings.trust_policy_id,
        traversals_store=traversals_store,
        clock=clock,
        id_generator=id_generator,
    )


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
