"""Clearance's update-handler factory (thin wrapper).

Closes over Clearance-specific knobs (stream type, codec, BC-local
`UnauthorizedError`, target-id attribute) and delegates to the
cross-BC `cora.infrastructure.update_handler.make_update_handler`.

## Hoist trigger

11a-a shipped no update-style handlers (only the create-style
`register_clearance` and the read-side `get_clearance`). 11a-b adds
six update-style transition handlers (`submit_clearance` /
`start_review_clearance` / `append_clearance_review_step` /
`approve_clearance` / `reject_clearance` / `activate_clearance`).
Six identical longhand bodies = clear rule-of-three signal; this
factory hoists the shared scaffolding so each slice's handler.py
shrinks to a 7-line `bind`. Mirrors `_supply_update_handler`
(hoisted at the rule-of-three trigger) and Operation's
`_procedure_update_handler` (hoisted at the rule-of-three trigger).

## Per-aggregate, not per-BC

Safety is a single-aggregate BC today (Clearance). The factory
scopes to the Clearance aggregate, not the BC, so a future
sibling aggregate (e.g., the deferred ClearanceTemplate; see
[[project_safety_clearance_design]] watch item) would get its own
factory rather than parameterizing this one.

## Clearance-side knobs closed over

  - `stream_type = "Clearance"`.
  - `target_id_attr = "clearance_id"` -- every Clearance transition
    command exposes `clearance_id: UUID`.
  - `unauthorized_error = UnauthorizedError` from the Safety BC.
  - The four codec functions imported from
    `cora.safety.aggregates.clearance`.
"""

from collections.abc import Callable, Sequence

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler
from cora.safety.aggregates.clearance import (
    ClearanceEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.safety.errors import UnauthorizedError


def make_clearance_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[ClearanceEvent]],
):
    """Build an update-style handler for one Clearance transition slice."""
    return make_update_handler(
        deps,
        stream_type="Clearance",
        target_id_attr="clearance_id",
        from_stored=from_stored,
        to_payload=to_payload,
        event_type_name=event_type_name,
        fold=fold,
        unauthorized_error=UnauthorizedError,
        command_name=command_name,
        log_prefix=log_prefix,
        decide_fn=decide_fn,
    )


__all__ = ["make_clearance_update_handler"]
