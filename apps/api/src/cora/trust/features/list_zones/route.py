"""HTTP route for the `list_zones` query slice.

`GET /zones?cursor=...&limit=50` returns
`{"items": [...], "next_cursor": "..." | null}`.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.trust.aggregates.zone import ZONE_NAME_MAX_LENGTH
from cora.trust.features.list_zones.handler import Handler
from cora.trust.features.list_zones.query import ListZones


class ZoneSummaryDTO(BaseModel):
    """One zone in a paginated list."""

    zone_id: UUID
    name: str = Field(..., max_length=ZONE_NAME_MAX_LENGTH)
    created_at: datetime


class ZoneListResponse(BaseModel):
    """Page of zones plus opaque next-page cursor."""

    items: list[ZoneSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.list_zones
    return handler


router = APIRouter(tags=["trust"])


@router.get(
    "/zones",
    status_code=status.HTTP_200_OK,
    response_model=ZoneListResponse,
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
    summary="List zones with cursor pagination",
)
async def list_zones(
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
) -> ZoneListResponse:
    page = await handler(
        ListZones(cursor=cursor, limit=limit),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return ZoneListResponse(
        items=[
            ZoneSummaryDTO(
                zone_id=item.zone_id,
                name=item.name,
                created_at=item.created_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
