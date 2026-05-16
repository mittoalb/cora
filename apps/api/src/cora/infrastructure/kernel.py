"""Process-wide dependency kernel.

`Kernel` carries the cross-BC primitives (settings, clock,
id_generator, authorize, event_store, idempotency_store) plus the
asyncpg `pool` (None for `app_env=test`). It's the "Shared Kernel"
in the DDD sense: a deliberately-shared set of dependencies every
bounded context's `wire_<bc>(deps)` function pulls from.

## Why this lives in its own module

This module has **zero BC imports**. That's the point: every BC's
wire / handler / route imports `Kernel` from here without
transitively pulling in any other BC. Phase-8d hardening: the
prior `Kernel` (then `SharedDeps`) lived alongside the production-
construction logic that lazy-imported `cora.trust` for the
authorize factory. That lazy import was tagged `deprecated = true`
in tach.toml because tach couldn't tell that the import was
control-flow-guarded. Splitting the data class out of the
construction module breaks the cycle at the namespace level:
`cora.infrastructure.kernel` only knows about ports, not adapters.

## BC-specific stores stay BC-internal

`Kernel` carries cross-BC primitives only. BC-specific entry
stores (Trust BC's `TraversalStore`, Decision BC's `ReasoningStore`,
etc.) are constructed inside each BC's own `wire_<bc>(deps)` from
`deps.pool` and live BC-internal. This keeps the kernel clean as
more BCs adopt the logbook-and-entries pattern.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import asyncpg

from cora.infrastructure.config import Settings
from cora.infrastructure.ports import (
    Authorize,
    ClearanceLookup,
    Clock,
    EventStore,
    IdempotencyStore,
    IdGenerator,
)


@dataclass(frozen=True)
class Kernel:
    """Process-wide dependencies. Immutable after construction.

    `pool` is the asyncpg connection pool (None when
    `app_env=test`). BCs that need additional Postgres-backed
    adapters (entry stores, projections, etc.) construct them in
    their own `wire_<bc>(deps)` from this pool, keeping BC-specific
    stores out of the kernel.

    `clearance_lookup` (Phase 11a-c-3): cross-BC port consumed by
    Run BC's `start_run` handler to gate Run.start on the presence
    of an Active Safety Clearance covering the Run's scope. Safety
    BC ships `PostgresClearanceLookup` as the production adapter
    (reads `proj_safety_clearance_summary`). Test environments
    default to `AlwaysCoveredClearanceLookup` (synthetic Active
    clearance bypass) so existing Run tests don't have to seed
    real clearances; gate-specific tests override with the real
    adapter explicitly. Mirrors the `Authorize` / `AllowAllAuthorize`
    test-default pattern.
    """

    settings: Settings
    clock: Clock
    id_generator: IdGenerator
    authorize: Authorize
    event_store: EventStore
    idempotency_store: IdempotencyStore
    clearance_lookup: ClearanceLookup
    pool: asyncpg.Pool | None = None


Teardown = Callable[[], Awaitable[None]]
"""Async callable returned by kernel-construction; the FastAPI
lifespan calls this to release pool resources at shutdown."""


__all__ = [
    "Kernel",
    "Teardown",
]
