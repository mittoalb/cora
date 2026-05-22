"""Production Authorize-port factory.

Builds the Authorize port adapter for the Kernel. Lives inside
`cora.trust` (not `cora.infrastructure`) so the BC that owns the
authz domain owns the construction wiring: `cora.infrastructure`
stays BC-free at the namespace level (no lazy import workarounds,
no tach `deprecated=true` exceptions).

`build_authorize` is what the composition root (`cora.api.main`)
passes to `build_kernel(...)` as the authorize factory, completing
the dependency direction: infrastructure does not know about BCs;
the composition root wires BCs into the kernel.

## Adapter selection

  - `Settings.trust_policy_id is None` -> `AllowAllAuthorize`
    (Phase 1 permissive default; matches dev/test posture).
  - `Settings.trust_policy_id` set -> `TrustAuthorize` gates every
    command through that single Policy aggregate. See
    `cora/trust/authorize.py` for the bootstrap workflow when
    first enabling real auth in a deployment.

## TraversalStore wiring

When `TrustAuthorize` is constructed, it receives the Trust BC's
`TraversalStore` so it can emit one `ConduitTraversal` row per
Allow / Deny decision. The store is built inline (Postgres if
the pool is set, in-memory otherwise) and passed in alongside
clock + id_generator. `AllowAllAuthorize` stays bare (no entries
from the permissive default).
"""

import asyncpg

from cora.infrastructure.config import Settings
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    Authorize,
    Clock,
    EventStore,
    IdGenerator,
)
from cora.trust.aggregates.conduit.entries import (
    InMemoryTraversalStore,
    PostgresTraversalStore,
    TraversalStore,
)
from cora.trust.authorize import TrustAuthorize


def build_authorize(
    settings: Settings,
    event_store: EventStore,
    *,
    pool: asyncpg.Pool | None,
    clock: Clock,
    id_generator: IdGenerator,
) -> Authorize:
    """Construct the production Authorize port for the Kernel."""
    if settings.trust_policy_id is None:
        return AllowAllAuthorize()

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


__all__ = ["build_authorize"]
