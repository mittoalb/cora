"""MCP tool for the `abandon_campaign` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.campaign._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.campaign.aggregates.campaign import CAMPAIGN_REASON_MAX_LENGTH
from cora.campaign.features.abandon_campaign.command import AbandonCampaign
from cora.campaign.features.abandon_campaign.handler import Handler
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class AbandonCampaignOutput(BaseModel):
    """Structured output of the `abandon_campaign` MCP tool."""

    campaign_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `abandon_campaign` tool on the given MCP server."""

    @mcp.tool(
        name="abandon_campaign",
        description=(
            "Abandon a Campaign (Planned | Active | Held -> Abandoned). "
            "Early-terminal with REQUIRED reason. Member Runs are NOT "
            "cascaded (per-Run audit independence). Members are locked "
            "after abandon."
        ),
    )
    async def abandon_campaign_tool(  # pyright: ignore[reportUnusedFunction]
        campaign_id: Annotated[UUID, Field(description="Target Campaign's id.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CAMPAIGN_REASON_MAX_LENGTH,
                description=(
                    "REQUIRED. Operator-supplied reason for the abandon "
                    "transition (audit-log breadcrumb)."
                ),
            ),
        ],
    ) -> AbandonCampaignOutput:
        handler = get_handler()
        await handler(
            AbandonCampaign(campaign_id=campaign_id, reason=reason),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return AbandonCampaignOutput(campaign_id=campaign_id)
