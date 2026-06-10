"""ClearanceTemplate's update-handler factory (thin wrapper).

Closes over ClearanceTemplate-specific knobs (stream type, codec,
BC-local `UnauthorizedError`, target-id attribute) and delegates to
the cross-BC `cora.infrastructure.update_handler.make_update_handler`.

## Hoist trigger

Shipped ahead of its rule-of-three quorum. The first ClearanceTemplate
transition slice (`activate_clearance_template`) cannot use this
factory because `ClearanceTemplateActivated` carries an `activated_by`
actor field that `make_update_handler` does not thread to `decide_fn`
today, so `activate_clearance_template/handler.py` stays LONGHAND. The
factory ships now so the next two transition slices
(`deprecate_clearance_template` and `withdraw_clearance_template`)
shipped in the follow-up arc can collapse to a 7-line `bind` if their
events stay actor-less, completing the rule-of-three. If either of
those events grows an actor field, the factory's `decide_fn` signature
will be widened then, not now.

## Per-aggregate, not per-BC

Safety now hosts two aggregates (Clearance and ClearanceTemplate). Each
gets its own factory rather than parameterizing a shared one, matching
the per-aggregate scoping rationale documented on
`_clearance_update_handler`.

## ClearanceTemplate-side knobs closed over

  - `stream_type = "ClearanceTemplate"`.
  - `target_id_attr = "template_id"` -- every ClearanceTemplate
    transition command exposes `template_id: UUID`.
  - `unauthorized_error = UnauthorizedError` from the Safety BC.
  - The four codec functions imported from
    `cora.safety.aggregates.clearance_template`.
"""

from collections.abc import Callable, Sequence

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.safety.errors import UnauthorizedError


def make_clearance_template_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[ClearanceTemplateEvent]],
):
    """Build an update-style handler for one ClearanceTemplate transition slice."""
    return make_update_handler(
        deps,
        stream_type="ClearanceTemplate",
        target_id_attr="template_id",
        from_stored=from_stored,
        to_payload=to_payload,
        event_type_name=event_type_name,
        fold=fold,
        unauthorized_error=UnauthorizedError,
        command_name=command_name,
        log_prefix=log_prefix,
        decide_fn=decide_fn,
    )


__all__ = ["make_clearance_template_update_handler"]
