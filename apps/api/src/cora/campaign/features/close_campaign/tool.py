"""MCP tool for the `close_campaign` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.campaign._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.campaign.features.close_campaign.command import CloseCampaign
from cora.campaign.features.close_campaign.handler import Handler
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class CloseCampaignOutput(BaseModel):
    """Structured output of the `close_campaign` MCP tool."""

    campaign_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `close_campaign` tool on the given MCP server."""

    @mcp.tool(
        name="close_campaign",
        description=(
            "Close a Campaign (Active | Held -> Closed). Normal terminal. "
            "Member Runs are NOT cascaded (per-Run audit independence). "
            "Members are locked after close."
        ),
    )
    async def close_campaign_tool(  # pyright: ignore[reportUnusedFunction]
        campaign_id: Annotated[UUID, Field(description="Target Campaign's id.")],
    ) -> CloseCampaignOutput:
        handler = get_handler()
        await handler(
            CloseCampaign(campaign_id=campaign_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return CloseCampaignOutput(campaign_id=campaign_id)
