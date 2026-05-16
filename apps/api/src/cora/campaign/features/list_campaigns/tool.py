"""MCP tool for the `list_campaigns` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.campaign._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.campaign.aggregates.campaign import (
    CAMPAIGN_NAME_MAX_LENGTH,
    CAMPAIGN_TAG_MAX_LENGTH,
    CampaignIntent,
    CampaignStatus,
)
from cora.campaign.features.list_campaigns.handler import Handler
from cora.campaign.features.list_campaigns.query import (
    CampaignIntentFilter,
    CampaignStatusFilter,
    ListCampaigns,
)
from cora.infrastructure.observability import current_correlation_id


class CampaignSummaryRow(BaseModel):
    campaign_id: UUID
    name: str = Field(..., max_length=CAMPAIGN_NAME_MAX_LENGTH)
    intent: CampaignIntent
    status: CampaignStatus
    lead_actor_id: UUID
    subject_id: UUID | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list[str])
    external_id: str | None = None
    run_count: int = 0
    registered_at: datetime
    started_at: datetime | None = None
    last_status_changed_at: datetime | None = None
    last_status_reason: str | None = None


class CampaignListOutput(BaseModel):
    """Structured output of the `list_campaigns` MCP tool."""

    items: list[CampaignSummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_campaigns` tool on the given MCP server."""

    @mcp.tool(
        name="list_campaigns",
        description=(
            "Cursor-paginated list of campaigns. Optional filters: "
            "`status` (defaults to OPEN set Planned+Active+Held; pass "
            "'all' to include Closed + Abandoned, or an exact value), "
            "`intent` (one of the 4 CampaignIntent values), "
            "`lead_actor_id`, `subject_id`, `tag` (exact match in the "
            "tags array). Pass `cursor` from a previous page's "
            "`next_cursor` to fetch the next page."
        ),
    )
    async def list_campaigns_tool(  # pyright: ignore[reportUnusedFunction]
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        status: Annotated[
            CampaignStatusFilter | None,
            Field(
                description=(
                    "Optional status filter; defaults to the OPEN set "
                    "(Planned + Active + Held). Pass 'all' to include "
                    "every status."
                ),
            ),
        ] = None,
        intent: Annotated[
            CampaignIntentFilter | None,
            Field(description="Optional intent filter; omit to list all intents."),
        ] = None,
        lead_actor_id: Annotated[
            UUID | None,
            Field(description="Optional lead-actor filter."),
        ] = None,
        subject_id: Annotated[
            UUID | None,
            Field(description="Optional subject filter."),
        ] = None,
        tag: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=CAMPAIGN_TAG_MAX_LENGTH,
                description="Optional tag filter (exact match in the tags array).",
            ),
        ] = None,
    ) -> CampaignListOutput:
        handler = get_handler()
        page = await handler(
            ListCampaigns(
                cursor=cursor,
                limit=limit,
                status=status,
                intent=intent,
                lead_actor_id=lead_actor_id,
                subject_id=subject_id,
                tag=tag,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return CampaignListOutput(
            items=[
                CampaignSummaryRow(
                    campaign_id=item.campaign_id,
                    name=item.name,
                    intent=CampaignIntent(item.intent),
                    status=CampaignStatus(item.status),
                    lead_actor_id=item.lead_actor_id,
                    subject_id=item.subject_id,
                    description=item.description,
                    tags=item.tags,
                    external_id=item.external_id,
                    run_count=item.run_count,
                    registered_at=item.registered_at,
                    started_at=item.started_at,
                    last_status_changed_at=item.last_status_changed_at,
                    last_status_reason=item.last_status_reason,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
