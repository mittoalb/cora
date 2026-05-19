"""Application handler for the `abandon_campaign` slice.

Update-style handler. Body lives in the per-aggregate factory at
`cora.campaign._campaign_update_handler.make_campaign_update_handler`.
"""

from typing import Protocol
from uuid import UUID

from cora.campaign._campaign_update_handler import make_campaign_update_handler
from cora.campaign.features.abandon_campaign.command import AbandonCampaign
from cora.campaign.features.abandon_campaign.decider import decide
from cora.infrastructure.kernel import Kernel

_NIL_SENTINEL_ID = UUID(int=0)


class Handler(Protocol):
    """Callable interface every abandon_campaign handler implements."""

    async def __call__(
        self,
        command: AbandonCampaign,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an abandon_campaign handler closed over the shared deps."""
    return make_campaign_update_handler(
        deps,
        command_name="AbandonCampaign",
        log_prefix="abandon_campaign",
        decide_fn=decide,
    )
