"""Application handler for the `close_campaign` slice.

Update-style handler. Body lives in the per-aggregate factory at
`cora.campaign._campaign_update_handler.make_campaign_update_handler`.
"""

from typing import Protocol
from uuid import UUID

from cora.campaign._campaign_update_handler import make_campaign_update_handler
from cora.campaign.features.close_campaign.command import CloseCampaign
from cora.campaign.features.close_campaign.decider import decide
from cora.infrastructure.kernel import Kernel


class Handler(Protocol):
    """Callable interface every close_campaign handler implements."""

    async def __call__(
        self,
        command: CloseCampaign,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a close_campaign handler closed over the shared deps."""
    return make_campaign_update_handler(
        deps,
        command_name="CloseCampaign",
        log_prefix="close_campaign",
        decide_fn=decide,
    )
