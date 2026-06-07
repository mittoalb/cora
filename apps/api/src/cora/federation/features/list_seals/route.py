"""HTTP route for the `list_seals` query slice.

`GET /federation/seals` accepts: `cursor`, `limit`, `status`. Returns
`{"items": [...], "next_cursor": "..." | null}`.

Seal is a singleton per facility, so this endpoint lists across
facilities (one row per facility). Filter set is intentionally tiny:
the row volume is bounded by facility count (~1-50). Per-row scoping
(operator confidentiality across facilities) deferred until ReBAC; the
current Authorize port gating is command-name only.

Cursor key uses the projection's `seal_stream_id` UUID column
(populated at INSERT time from `facility_id` via `seal_stream_id`).
The column is internal to the read model and is intentionally NOT
surfaced on `SealSummaryDTO` because callers already have
`facility_id`, and the stream id is a derived identifier.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel

from cora.federation.aggregates.seal.state import SealStatus
from cora.federation.features.list_seals.handler import Handler
from cora.federation.features.list_seals.query import ListSeals, SealStatusFilter
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class SealSummaryDTO(BaseModel):
    """One Seal singleton in a paginated list."""

    facility_id: str
    online_credential_id: UUID
    offline_credential_id: UUID
    current_head_hash: str | None = None
    current_sequence_number: int
    initialized_by: UUID
    last_signed_by: UUID | None = None
    status: SealStatus
    initialized_at: datetime
    last_signed_at: datetime | None = None


class SealListResponse(BaseModel):
    """Page of Seal singletons plus opaque next-page cursor."""

    items: list[SealSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.list_seals
    return handler


router = APIRouter(tags=["federation"])


@router.get(
    "/federation/seals",
    status_code=status.HTTP_200_OK,
    response_model=SealListResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Query parameters failed validation OR `cursor` was malformed.",
        },
    },
    summary=(
        "List Seal singletons (one per facility) with cursor pagination + optional status filter."
    ),
)
async def list_seals(
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
    status_filter: Annotated[
        SealStatusFilter | None,
        Query(
            alias="status",
            description="Optional status filter (Live or Republishing).",
        ),
    ] = None,
) -> SealListResponse:
    page = await handler(
        ListSeals(cursor=cursor, limit=limit, status=status_filter),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return SealListResponse(
        items=[
            SealSummaryDTO(
                facility_id=item.facility_id,
                online_credential_id=item.online_credential_id,
                offline_credential_id=item.offline_credential_id,
                current_head_hash=item.current_head_hash,
                current_sequence_number=item.current_sequence_number,
                initialized_by=item.initialized_by,
                last_signed_by=item.last_signed_by,
                status=SealStatus(item.status),
                initialized_at=item.initialized_at,
                last_signed_at=item.last_signed_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )


__all__ = ["SealListResponse", "SealSummaryDTO", "router"]
