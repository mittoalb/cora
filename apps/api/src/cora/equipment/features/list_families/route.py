"""HTTP route for the `list_families` query slice.

`GET /families?cursor=...&limit=50&status=Versioned` returns
`{"items": [...], "next_cursor": "..." | null}`.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.family import (
    FAMILY_NAME_MAX_LENGTH,
    FAMILY_VERSION_TAG_MAX_LENGTH,
)
from cora.equipment.features.list_families.handler import Handler
from cora.equipment.features.list_families.query import (
    FamilyStatusFilter,
    ListFamilies,
)
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


class FamilySummaryDTO(BaseModel):
    """One family in a paginated list."""

    family_id: UUID
    name: str = Field(..., max_length=FAMILY_NAME_MAX_LENGTH)
    status: FamilyStatusFilter
    version_tag: str | None = Field(default=None, max_length=FAMILY_VERSION_TAG_MAX_LENGTH)
    created_at: datetime


class FamilyListResponse(BaseModel):
    """Page of families plus opaque next-page cursor."""

    items: list[FamilySummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.list_families
    return handler


router = APIRouter(tags=["equipment"])


@router.get(
    "/families",
    status_code=status.HTTP_200_OK,
    response_model=FamilyListResponse,
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
    summary="List families with cursor pagination + status filter",
)
async def list_families(
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
        FamilyStatusFilter | None,
        Query(
            alias="status",
            description=(
                "Optional status filter (one of: Defined, Versioned, "
                "Deprecated). Omit to return all statuses."
            ),
        ),
    ] = None,
) -> FamilyListResponse:
    page = await handler(
        ListFamilies(cursor=cursor, limit=limit, status=status_filter),
        principal_id=principal_id,
        correlation_id=cid,
    )
    return FamilyListResponse(
        items=[
            FamilySummaryDTO(
                family_id=item.family_id,
                name=item.name,
                status=item.status,  # type: ignore[arg-type]
                version_tag=item.version_tag,
                created_at=item.created_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
