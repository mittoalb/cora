"""MCP tool for the `add_run_to_campaign` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.campaign._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.campaign.features.add_run_to_campaign.command import AddRunToCampaign
from cora.campaign.features.add_run_to_campaign.handler import Handler
from cora.infrastructure.observability import current_correlation_id


class AddRunToCampaignOutput(BaseModel):
    """Structured output of the `add_run_to_campaign` MCP tool."""

    campaign_id: UUID
    run_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `add_run_to_campaign` tool on the given MCP server."""

    @mcp.tool(
        name="add_run_to_campaign",
        description=(
            "Add a Run as a member of a Campaign (atomic two-stream write). "
            "Campaign must be in Planned, Active, or Held; Run must not "
            "already be assigned to a (different) Campaign. Writes both "
            "streams via EventStore.append_streams (all-or-nothing)."
        ),
    )
    async def add_run_to_campaign_tool(  # pyright: ignore[reportUnusedFunction]
        campaign_id: Annotated[UUID, Field(description="Target Campaign's id.")],
        run_id: Annotated[UUID, Field(description="Run to add as a member.")],
    ) -> AddRunToCampaignOutput:
        handler = get_handler()
        await handler(
            AddRunToCampaign(campaign_id=campaign_id, run_id=run_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return AddRunToCampaignOutput(campaign_id=campaign_id, run_id=run_id)
