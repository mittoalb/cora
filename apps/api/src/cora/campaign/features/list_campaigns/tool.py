"""MCP tool for the `list_campaigns` query slice.

Mirrors the REST route's behavior including the OPEN-set default
([Planned, Active, Held]) and the `status=all` sentinel. The
defaults MUST match the REST surface; agents and operators see the
same filtered view so a bug surfaced in one client surfaces in the
other.

User-facing translation (default OPEN set, 'all' sentinel) lives
here at the tool boundary; the application handler sees only
canonical list-typed filters per the
`cora.infrastructure.list_query` growth-rule discipline.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

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
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id

# Tool-surface type for status, matching the route's `_RouteStatusParam`
# semantics: real values plus the 'all' sentinel.
_ToolStatusParam = Literal["Planned", "Active", "Held", "Closed", "Abandoned", "all"]

# Same OPEN-set default as the route. Kept duplicated rather than
# imported from route.py to avoid coupling tool layer to route layer
# (both depend on the same domain default, neither depends on the other).
_OPEN_STATUSES: list[CampaignStatusFilter] = ["Planned", "Active", "Held"]


class _ListCampaignsInputError(ValueError):
    """Raised when caller passes conflicting status inputs ('all' mixed
    with explicit status values). MCP runtime surfaces ValueError as a
    tool error, parallel to the REST route's HTTPException(422)."""


def _resolve_statuses(
    status_params: list[_ToolStatusParam] | None,
) -> list[CampaignStatusFilter] | None:
    """Mirror of `route._resolve_statuses`. See route docstring.

    Default (None or empty) -> OPEN set [Planned, Active, Held], same
    as the REST route.
    """
    if status_params is None or len(status_params) == 0:
        return list(_OPEN_STATUSES)
    has_all = "all" in status_params
    if has_all and len(status_params) > 1:
        raise _ListCampaignsInputError(
            "Pass either `status=all` (disable filter) or one or "
            "more explicit status values, not both."
        )
    if has_all:
        return None
    return [v for v in status_params if v != "all"]


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
            "`status` (one or more values; defaults to OPEN set "
            "[Planned, Active, Held]; pass ['all'] alone to include "
            "every status), `intent` (one of the 4 CampaignIntent "
            "values), `lead_actor_id`, `subject_id`, `tag` (exact "
            "match in the tags array). Pass `cursor` from a previous "
            "page's `next_cursor` to fetch the next page."
        ),
    )
    async def list_campaigns_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        status: Annotated[
            list[_ToolStatusParam] | None,
            Field(
                description=(
                    "Optional status filter; multi-value; defaults to "
                    "the OPEN set [Planned, Active, Held]. Pass ['all'] "
                    "alone to include every status."
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
        statuses = _resolve_statuses(status)
        handler = get_handler()
        page = await handler(
            ListCampaigns(
                cursor=cursor,
                limit=limit,
                statuses=statuses,
                intent=intent,
                lead_actor_id=lead_actor_id,
                subject_id=subject_id,
                tag=tag,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
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
