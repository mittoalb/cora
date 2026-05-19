"""HTTP route for the `list_campaigns` query slice.

`GET /campaigns` accepts these optional query params: `cursor`,
`limit`, `status` (one or more; multi-value; plus the `all`
sentinel that disables the filter), `intent`, `lead_actor_id`,
`subject_id`, `tag`.

## Status default + 'all' sentinel

Omitted `status` defaults to the OPEN set (`[Planned, Active,
Held]`) so operators don't see Closed + Abandoned terminal
campaigns cluttering the list. Pass `?status=all` to opt into the
full set. Pass one or more explicit values
(`?status=Planned&status=Active`) to narrow further.

`all` and explicit status values cannot be combined in the same
request; doing so returns 422.

The application handler sees only the canonical `statuses` list;
the OPEN-set default and the 'all' sentinel both converge to the
same internal contract per the `cora.infrastructure.list_query`
growth-rule discipline (mirrors the list_cautions force-conform).
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)

# Route-surface type: real status values plus the 'all' sentinel that
# translates to "no filter" at this layer. The query dataclass +
# application handler never see 'all' (per the growth-rule discipline
# documented on `cora.infrastructure.list_query`).
_RouteStatusParam = Literal["Planned", "Active", "Held", "Closed", "Abandoned", "all"]

# OPEN-set default: Planned + Active + Held. Terminal states (Closed,
# Abandoned) hidden by default; operator opts in via `?status=all` or
# explicit terminal values.
_OPEN_STATUSES: list[CampaignStatusFilter] = ["Planned", "Active", "Held"]


def _resolve_statuses(
    status_params: list[_RouteStatusParam] | None,
) -> list[CampaignStatusFilter] | None:
    """Translate user-facing status inputs into the canonical list.

    None (omitted) -> OPEN-set default [Planned, Active, Held].

    Exactly ['all'] -> None (disable the filter; show every status).
    'all' mixed with real values raises 422 (ambiguous).

    Otherwise -> the explicit list (after validating no 'all' sneaked
    in alongside real values).
    """
    if status_params is None or len(status_params) == 0:
        return list(_OPEN_STATUSES)
    has_all = "all" in status_params
    if has_all and len(status_params) > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Pass either `status=all` (disable filter) or one or "
                "more explicit status values, not both."
            ),
        )
    if has_all:
        return None
    return [v for v in status_params if v != "all"]


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
                "malformed OR `status=all` was mixed with explicit values."
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
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    cursor: Annotated[
        str | None,
        Query(description="Opaque cursor from a previous page's `next_cursor`."),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Page size; capped at 100."),
    ] = 50,
    status_params: Annotated[
        list[_RouteStatusParam] | None,
        Query(
            alias="status",
            description=(
                "Optional status filter; multi-value. Omit to default "
                "to the OPEN set ([Planned, Active, Held]). Pass `all` "
                "alone to include every status, or one or more explicit "
                "values to narrow. `all` cannot be mixed with explicit "
                "values."
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
    statuses = _resolve_statuses(status_params)
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
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
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
