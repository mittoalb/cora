"""Application handler for the `resume_campaign` slice.

Update-style handler. Body lives in the per-aggregate factory at
`cora.campaign._campaign_update_handler.make_campaign_update_handler`.
"""

from typing import Protocol
from uuid import UUID

from cora.campaign._campaign_update_handler import make_campaign_update_handler
from cora.campaign.features.resume_campaign.command import ResumeCampaign
from cora.campaign.features.resume_campaign.decider import decide
from cora.infrastructure.kernel import Kernel


class Handler(Protocol):
    """Callable interface every resume_campaign handler implements."""

    async def __call__(
        self,
        command: ResumeCampaign,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a resume_campaign handler closed over the shared deps."""
    return make_campaign_update_handler(
        deps,
        command_name="ResumeCampaign",
        log_prefix="resume_campaign",
        decide_fn=decide,
    )
