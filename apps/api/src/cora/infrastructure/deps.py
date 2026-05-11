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

## Phase 6f-5a: TraversalStore wiring

The Trust BC's per-Conduit authz traversal observation log is wired
here too. Mirrors the EventStore selection: in-memory for `app_env=test`,
Postgres for production. When `trust_policy_id` is set, the
TrustAuthorize adapter receives the TraversalStore + Clock +
IdGenerator and emits one observation row per Allow / Deny decision.
The AllowAllAuthorize fallback skips emission entirely.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

# `TraversalStore` adapters are imported lazily at call sites below
# to avoid a circular import: `cora.trust.aggregates.conduit.observations`
# itself is leaf-clean, but Python loads `cora.trust.__init__` whenever
# any submodule under `cora.trust` is referenced — and that __init__
# transitively pulls `cora.trust.wire` → handlers → `cora.infrastructure.deps`.
# Same lazy-import pattern used for `TrustAuthorize` in `_build_authorize`.
#
# Protocol is referenced via TYPE_CHECKING for the SharedDeps annotation.
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:  # pragma: no cover
    from cora.trust.aggregates.conduit.observations import TraversalStore


def _default_traversals_store() -> "TraversalStore":
    """Default-factory shim for SharedDeps.traversals_store.

    Lazy-imports the InMemory adapter to avoid the deps.py ↔ trust
    circular import described at the top of this module.
    """
    from cora.trust.aggregates.conduit.observations import InMemoryTraversalStore

    return InMemoryTraversalStore()


@dataclass(frozen=True)
class SharedDeps:
    """Process-wide dependencies. Immutable after `build_shared_deps` returns.

    `traversals_store` defaults to an InMemory adapter so test
    constructions of `SharedDeps` (which predate Phase 6f-5a) don't
    need explicit wiring. Production builds via `build_shared_deps`
    always overwrite with the env-appropriate adapter (Postgres for
    non-test, InMemory for `app_env=test`).
    """

    settings: Settings
    clock: Clock
    id_generator: IdGenerator
    authorize: Authorize
    event_store: EventStore
    idempotency_store: IdempotencyStore
    traversals_store: "TraversalStore" = field(default_factory=_default_traversals_store)


Teardown = Callable[[], Awaitable[None]]


async def build_shared_deps() -> tuple[SharedDeps, Teardown]:
    """Construct shared dependencies. Called once from the FastAPI lifespan."""
    settings = Settings()  # type: ignore[call-arg]  # Pydantic loads from env
    configure_logging(settings.log_level)
    event_store, idempotency_store, traversals_store, teardown = await _build_stores(settings)
    clock = SystemClock()
    id_generator = UUIDv7Generator()
    deps = SharedDeps(
        settings=settings,
        clock=clock,
        id_generator=id_generator,
        authorize=_build_authorize(
            settings,
            event_store,
            traversals_store=traversals_store,
            clock=clock,
            id_generator=id_generator,
        ),
        event_store=event_store,
        idempotency_store=idempotency_store,
        traversals_store=traversals_store,
    )
    return deps, teardown


def _build_authorize(
    settings: Settings,
    event_store: EventStore,
    *,
    traversals_store: "TraversalStore",
    clock: Clock,
    id_generator: IdGenerator,
) -> Authorize:
    """Choose the Authorize adapter based on Settings.

    `trust_policy_id` unset (None) → `AllowAllAuthorize` (Phase 1
    permissive default; matches dev/test). Set → `TrustAuthorize` gates
    every command through that single Policy aggregate. See
    `cora/trust/authorize.py` for the bootstrap workflow when first
    enabling real auth in a deployment.

    `TrustAuthorize` is imported lazily because `cora.trust.__init__`
    transitively imports `SharedDeps` from this module (via
    `cora.trust.wire` → handlers); a top-level import here would
    trigger a partially-initialized-module circular import. Splitting
    `SharedDeps` into a separate module would also fix it but is a
    bigger refactor; the lazy import is local to one function.

    Phase 6f-5a: when `TrustAuthorize` is wired, also pass the
    traversals_store + clock + id_generator so it can emit per-decision
    ConduitTraversal observations. AllowAllAuthorize stays bare (no
    observations from the permissive default).
    """
    if settings.trust_policy_id is None:
        return AllowAllAuthorize()
    from cora.trust.authorize import TrustAuthorize

    return TrustAuthorize(
        event_store,
        policy_id=settings.trust_policy_id,
        traversals_store=traversals_store,
        clock=clock,
        id_generator=id_generator,
    )


async def _build_stores(
    settings: Settings,
) -> tuple[EventStore, IdempotencyStore, "TraversalStore", Teardown]:
    # Lazy import to break the deps.py ↔ trust circular import
    # (see module-level note).
    from cora.trust.aggregates.conduit.observations import (
        InMemoryTraversalStore,
        PostgresTraversalStore,
    )

    if settings.app_env == "test":
        return (
            InMemoryEventStore(),
            InMemoryIdempotencyStore(),
            InMemoryTraversalStore(),
            _noop_teardown,
        )

    pool = await create_pool(
        settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
    )
    return (
        PostgresEventStore(pool),
        PostgresIdempotencyStore(pool),
        PostgresTraversalStore(pool),
        _make_pool_teardown(pool),
    )


async def _noop_teardown() -> None:
    return None


def _make_pool_teardown(pool: asyncpg.Pool) -> Teardown:
    async def teardown() -> None:
        await pool.close()

    return teardown
