"""Application handler for the `hold_campaign` slice.

Update-style handler. Body lives in the per-aggregate factory at
`cora.campaign._campaign_update_handler.make_campaign_update_handler`.
"""

from typing import Protocol
from uuid import UUID

from cora.campaign._campaign_update_handler import make_campaign_update_handler
from cora.campaign.features.hold_campaign.command import HoldCampaign
from cora.campaign.features.hold_campaign.decider import decide
from cora.infrastructure.kernel import Kernel


class Handler(Protocol):
    """Callable interface every hold_campaign handler implements."""

    async def __call__(
        self,
        command: HoldCampaign,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a hold_campaign handler closed over the shared deps."""
    return make_campaign_update_handler(
        deps,
        command_name="HoldCampaign",
        log_prefix="hold_campaign",
        decide_fn=decide,
    )
