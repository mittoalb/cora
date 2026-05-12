"""HTTP route for the `list_capabilities` query slice.

`GET /capabilities?cursor=...&limit=50&status=Versioned` returns
`{"items": [...], "next_cursor": "..." | null}`.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.capability import (
    CAPABILITY_NAME_MAX_LENGTH,
    CAPABILITY_VERSION_TAG_MAX_LENGTH,
)
from cora.equipment.features.list_capabilities.handler import Handler
from cora.equipment.features.list_capabilities.query import (
    CapabilityStatusFilter,
    ListCapabilities,
)
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


class CapabilitySummaryDTO(BaseModel):
    """One capability in a paginated list."""

    capability_id: UUID
    name: str = Field(..., max_length=CAPABILITY_NAME_MAX_LENGTH)
    status: CapabilityStatusFilter
    version_tag: str | None = Field(default=None, max_length=CAPABILITY_VERSION_TAG_MAX_LENGTH)
    created_at: datetime


class CapabilityListResponse(BaseModel):
    """Page of capabilities plus opaque next-page cursor."""

    items: list[CapabilitySummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.list_capabilities
    return handler


router = APIRouter(tags=["equipment"])


@router.get(
    "/capabilities",
    status_code=status.HTTP_200_OK,
    response_model=CapabilityListResponse,
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
    summary="List capabilities with cursor pagination + status filter",
)
async def list_capabilities(
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
        CapabilityStatusFilter | None,
        Query(
            alias="status",
            description=(
                "Optional status filter (one of: Defined, Versioned, "
                "Deprecated). Omit to return all statuses."
            ),
        ),
    ] = None,
) -> CapabilityListResponse:
    page = await handler(
        ListCapabilities(cursor=cursor, limit=limit, status=status_filter),
        principal_id=principal_id,
        correlation_id=cid,
    )
    return CapabilityListResponse(
        items=[
            CapabilitySummaryDTO(
                capability_id=item.capability_id,
                name=item.name,
                status=item.status,  # type: ignore[arg-type]
                version_tag=item.version_tag,
                created_at=item.created_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
