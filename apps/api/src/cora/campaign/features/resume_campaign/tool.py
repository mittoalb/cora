"""MCP tool for the `resume_campaign` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.campaign._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.campaign.features.resume_campaign.command import ResumeCampaign
from cora.campaign.features.resume_campaign.handler import Handler
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class ResumeCampaignOutput(BaseModel):
    """Structured output of the `resume_campaign` MCP tool."""

    campaign_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `resume_campaign` tool on the given MCP server."""

    @mcp.tool(
        name="resume_campaign",
        description=(
            "Resume a Held Campaign (Held -> Active). Single-source from "
            "Held. The prior hold reason is preserved on the aggregate "
            "for audit continuity."
        ),
    )
    async def resume_campaign_tool(  # pyright: ignore[reportUnusedFunction]
        campaign_id: Annotated[UUID, Field(description="Target Campaign's id.")],
    ) -> ResumeCampaignOutput:
        handler = get_handler()
        await handler(
            ResumeCampaign(campaign_id=campaign_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ResumeCampaignOutput(campaign_id=campaign_id)
