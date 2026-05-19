"""MCP tool for the `start_campaign` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.campaign._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.campaign.features.start_campaign.command import StartCampaign
from cora.campaign.features.start_campaign.handler import Handler
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class StartCampaignOutput(BaseModel):
    """Structured output of the `start_campaign` MCP tool."""

    campaign_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `start_campaign` tool on the given MCP server."""

    @mcp.tool(
        name="start_campaign",
        description=(
            "Start a Planned Campaign (Planned -> Active). Single-source "
            "from Planned. Members remain addable in Active."
        ),
    )
    async def start_campaign_tool(  # pyright: ignore[reportUnusedFunction]
        campaign_id: Annotated[UUID, Field(description="Target Campaign's id.")],
    ) -> StartCampaignOutput:
        handler = get_handler()
        await handler(
            StartCampaign(campaign_id=campaign_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return StartCampaignOutput(campaign_id=campaign_id)
