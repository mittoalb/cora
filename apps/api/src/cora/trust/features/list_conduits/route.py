"""HTTP route for the `list_conduits` query slice.

`GET /conduits?cursor=...&limit=50&source_zone_id=...&target_zone_id=...`
returns `{"items": [...], "next_cursor": "..." | null}`.
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
from cora.trust.aggregates.conduit import CONDUIT_NAME_MAX_LENGTH
from cora.trust.features.list_conduits.handler import Handler
from cora.trust.features.list_conduits.query import ListConduits


class ConduitSummaryDTO(BaseModel):
    """One conduit in a paginated list."""

    conduit_id: UUID
    name: str = Field(..., max_length=CONDUIT_NAME_MAX_LENGTH)
    source_zone_id: UUID
    target_zone_id: UUID
    created_at: datetime


class ConduitListResponse(BaseModel):
    """Page of conduits plus opaque next-page cursor."""

    items: list[ConduitSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.list_conduits
    return handler


router = APIRouter(tags=["trust"])


@router.get(
    "/conduits",
    status_code=status.HTTP_200_OK,
    response_model=ConduitListResponse,
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
    summary="List conduits with cursor pagination + endpoint filters",
)
async def list_conduits(
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
    source_zone_id: Annotated[
        UUID | None,
        Query(description="Optional source-zone filter; omit for any source."),
    ] = None,
    target_zone_id: Annotated[
        UUID | None,
        Query(description="Optional target-zone filter; omit for any target."),
    ] = None,
) -> ConduitListResponse:
    page = await handler(
        ListConduits(
            cursor=cursor,
            limit=limit,
            source_zone_id=source_zone_id,
            target_zone_id=target_zone_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return ConduitListResponse(
        items=[
            ConduitSummaryDTO(
                conduit_id=item.conduit_id,
                name=item.name,
                source_zone_id=item.source_zone_id,
                target_zone_id=item.target_zone_id,
                created_at=item.created_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
