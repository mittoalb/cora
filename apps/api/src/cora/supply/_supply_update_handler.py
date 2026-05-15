"""Supply's update-handler factory (thin wrapper).

Closes over Supply-specific knobs (stream type, codec, BC-local
`UnauthorizedError`, target-id attribute) and delegates to the
cross-BC `cora.infrastructure.update_handler.make_update_handler`.

## Hoist trigger

10a-a shipped one update-style handler (`mark_supply_available`)
longhand because rule-of-three hadn't fired yet. 10a-b adds 4 more
transition handlers (degrade / mark_unavailable / mark_recovering /
restore). Five identical longhand bodies = clear rule-of-three
signal; this factory hoists the shared scaffolding so each slice's
handler.py shrinks from ~120 lines to a 7-line `bind` that supplies
two strings and the decider. Mirrors `_asset_update_handler` (Asset
hoisted at 5e after 4 byte-identical slices) and Subject's
`_update_handler`.

## Per-aggregate, not per-BC

Supply is a single-aggregate BC today; the factory still scopes to
the Supply aggregate (not the BC) so a future Supply-sibling
aggregate would get its own factory rather than parameterizing this
one. Same per-aggregate scoping rationale as
`_asset_update_handler`.

## Supply-side knobs closed over

  - `stream_type = "Supply"`.
  - `target_id_attr = "supply_id"` — every Supply transition command
    exposes `supply_id: UUID` (MarkSupplyAvailable / DegradeSupply /
    MarkSupplyUnavailable / MarkSupplyRecovering / RestoreSupply).
  - `unauthorized_error = UnauthorizedError` from the Supply BC.
  - The four codec functions imported from
    `cora.supply.aggregates.supply`.

The transition slices carry `reason: str` alongside `supply_id`.
That field IS captured on the emitted event payload but is
intentionally NOT logged at the handler boundary (the event-store
stream is the source of truth for audit; handler log lines stay
shape-stable across slices). Same convention as Asset's condition
slices.
"""

from collections.abc import Callable, Sequence

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler
from cora.supply.aggregates.supply import (
    SupplyEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.supply.errors import UnauthorizedError


def make_supply_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[SupplyEvent]],
):
    """Build an update-style handler for one Supply transition slice."""
    return make_update_handler(
        deps,
        stream_type="Supply",
        target_id_attr="supply_id",
        from_stored=from_stored,
        to_payload=to_payload,
        event_type_name=event_type_name,
        fold=fold,
        unauthorized_error=UnauthorizedError,
        command_name=command_name,
        log_prefix=log_prefix,
        decide_fn=decide_fn,
    )


__all__ = ["make_supply_update_handler"]
