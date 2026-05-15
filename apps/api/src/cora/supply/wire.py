"""Compose the Supply BC's handlers from `Kernel`.

`wire_supply(deps)` is invoked once from the FastAPI lifespan and
the returned `SupplyHandlers` bundle is stored on
`app.state.supply`. Routes and MCP tools pull their handler out of
that bundle. New slices add a new field on `SupplyHandlers` and a
single line in this factory.

Cross-cutting decorators applied here mirror Access / Trust /
Subject / Equipment (composition order matters — innermost first):

1. `bind(deps)` — bare handler.
2. `with_idempotency` (create-style commands only) — Idempotency-Key
   support. Wrapped before tracing so cache-hits and cache-misses
   both attribute to the tracing span.
3. `with_tracing` — OTel span around every handler call. Records
   `cora.bc`, `cora.command` / `cora.query` attributes.

## Phase 10a-a scope

Four handlers wired:
  - `register_supply` (create-style; idempotency-wrapped)
  - `mark_supply_available` (transition; bare)
  - `get_supply` (query; bare)
  - `list_supplies` (query; bare)

The `mark_supply_available` handler is the only update-style
transition in 10a-a. The `make_supply_update_handler` factory hoist
(mirroring `_asset_update_handler`) is deferred until 10a-b's 4
transition slices land — rule of three triggers there, not here.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing
from cora.supply.features import (
    get_supply,
    list_supplies,
    mark_supply_available,
    register_supply,
)

_BC = "supply"


@dataclass(frozen=True)
class SupplyHandlers:
    """The Supply BC's handler bundle, each closed over Kernel.

    Phase 10a-a ships `register_supply` (create-style; idempotency-
    wrapped), `mark_supply_available` (transition; longhand bare),
    `get_supply` (query), and `list_supplies` (query). Phase 10a-b
    adds 4 more transition handlers; the per-aggregate
    `make_supply_update_handler` factory hoists at that point.
    """

    register_supply: register_supply.IdempotentHandler
    mark_supply_available: mark_supply_available.Handler
    get_supply: get_supply.Handler
    list_supplies: list_supplies.Handler


def wire_supply(deps: Kernel) -> SupplyHandlers:
    """Build the Supply BC handlers from shared dependencies."""
    return SupplyHandlers(
        register_supply=with_tracing(
            with_idempotency(
                register_supply.bind(deps),
                deps.idempotency_store,
                command_name="RegisterSupply",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterSupply",
            bc=_BC,
        ),
        mark_supply_available=with_tracing(
            mark_supply_available.bind(deps),
            command_name="MarkSupplyAvailable",
            bc=_BC,
        ),
        get_supply=with_tracing(
            get_supply.bind(deps),
            command_name="GetSupply",
            bc=_BC,
            kind="query",
        ),
        list_supplies=with_tracing(
            list_supplies.bind(deps),
            command_name="ListSupplies",
            bc=_BC,
            kind="query",
        ),
    )
