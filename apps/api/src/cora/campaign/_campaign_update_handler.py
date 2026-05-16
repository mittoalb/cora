"""Campaign's update-handler factory (thin wrapper).

Closes over Campaign-specific knobs (stream type, codec, BC-local
`UnauthorizedError`, target-id attribute) and delegates to the
cross-BC `cora.infrastructure.update_handler.make_update_handler`.

## Hoist trigger

6i-a ships five transition slices day-one (`start_campaign` /
`hold_campaign` / `resume_campaign` / `close_campaign` /
`abandon_campaign`). Five identical longhand bodies clearly fire
the rule-of-three signal at slice-creation time, so the factory
hoists immediately rather than after the first ship. Mirrors
`_clearance_update_handler` (Safety BC, hoisted at 11a-c-1 once
six transition slices arrived) and `_supply_update_handler` (Supply
BC, hoisted at 10a-b once five transition slices arrived).

## Per-aggregate, not per-BC

Campaign is a single-aggregate BC today. The factory still scopes
to the Campaign aggregate (not the BC) so a future Campaign-sibling
aggregate would get its own factory rather than parameterizing this
one. Same per-aggregate scoping rationale as `_clearance_update_handler`.

## Campaign-side knobs closed over

  - `stream_type = "Campaign"`.
  - `target_id_attr = "campaign_id"` -- every Campaign transition
    command exposes `campaign_id: UUID`.
  - `unauthorized_error = UnauthorizedError` from the Campaign BC.
  - The four codec functions imported from
    `cora.campaign.aggregates.campaign`.
"""

from collections.abc import Callable, Sequence

from cora.campaign.aggregates.campaign import (
    CampaignEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.campaign.errors import UnauthorizedError
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler


def make_campaign_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[CampaignEvent]],
):
    """Build an update-style handler for one Campaign transition slice."""
    return make_update_handler(
        deps,
        stream_type="Campaign",
        target_id_attr="campaign_id",
        from_stored=from_stored,
        to_payload=to_payload,
        event_type_name=event_type_name,
        fold=fold,
        unauthorized_error=UnauthorizedError,
        command_name=command_name,
        log_prefix=log_prefix,
        decide_fn=decide_fn,
    )


__all__ = ["make_campaign_update_handler"]
