"""HTTP route for the `list_campaigns` query slice.

`GET /campaigns` accepts these optional query params: `cursor`,
`limit`, `status`, `intent`, `lead_actor_id`, `subject_id`, `tag`.
Returns `{"items": [...], "next_cursor": "..." | null}`.

**Default behavior is `status` -> OPEN set (Planned + Active + Held).**
Pass `status=all` to include Closed + Abandoned (per the design memo:
terminal states never appear by default). Pass an exact status value
to narrow further.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
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
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


class CampaignSummaryDTO(BaseModel):
    """One campaign in a paginated list."""

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


class CampaignListPageResponse(BaseModel):
    """Page of campaigns plus opaque next-page cursor."""

    items: list[CampaignSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.campaign.list_campaigns
    return handler


router = APIRouter(tags=["campaign"])


@router.get(
    "/campaigns",
    status_code=status.HTTP_200_OK,
    response_model=CampaignListPageResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Query parameters failed validation OR `cursor` was "
                "malformed (corrupt base64, missing separator, bad "
                "timestamp / UUID)."
            ),
        },
    },
    summary=(
        "List campaigns with cursor pagination + status / intent / "
        "lead_actor_id / subject_id / tag filters. Defaults to the "
        "OPEN set (Planned + Active + Held); pass status=all for the "
        "full set including Closed + Abandoned."
    ),
)
async def list_campaigns(
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    cursor: Annotated[
        str | None,
        Query(description="Opaque cursor from a previous page's `next_cursor`."),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Page size; capped at 100."),
    ] = 50,
    status_filter: Annotated[
        CampaignStatusFilter | None,
        Query(
            alias="status",
            description=(
                "Optional status filter; omit to default to the OPEN "
                "set (Planned + Active + Held; hides Closed + "
                "Abandoned). Pass 'all' to include every status, or an "
                "exact value (Planned / Active / Held / Closed / "
                "Abandoned) to narrow."
            ),
        ),
    ] = None,
    intent: Annotated[
        CampaignIntentFilter | None,
        Query(description="Optional intent filter (one of the 4 CampaignIntent values)."),
    ] = None,
    lead_actor_id: Annotated[
        UUID | None,
        Query(description="Optional lead-actor filter ('campaigns I lead')."),
    ] = None,
    subject_id: Annotated[
        UUID | None,
        Query(description="Optional subject filter (loose ref)."),
    ] = None,
    tag: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=CAMPAIGN_TAG_MAX_LENGTH,
            description=(
                "Optional tag filter; matches any campaign whose tags array contains this value."
            ),
        ),
    ] = None,
) -> CampaignListPageResponse:
    page = await handler(
        ListCampaigns(
            cursor=cursor,
            limit=limit,
            status=status_filter,
            intent=intent,
            lead_actor_id=lead_actor_id,
            subject_id=subject_id,
            tag=tag,
        ),
        principal_id=principal_id,
        correlation_id=cid,
    )
    return CampaignListPageResponse(
        items=[
            CampaignSummaryDTO(
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


__all__ = ["CampaignListPageResponse", "CampaignSummaryDTO", "router"]
