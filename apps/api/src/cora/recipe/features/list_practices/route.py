"""HTTP route for the `list_practices` query slice.

`GET /practices?cursor=...&limit=50&status=Versioned&method_id=<uuid>`
returns `{"items": [...], "next_cursor": "..." | null}`.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.recipe.aggregates.practice import (
    PRACTICE_NAME_MAX_LENGTH,
    PRACTICE_VERSION_TAG_MAX_LENGTH,
)
from cora.recipe.features.list_practices.handler import Handler
from cora.recipe.features.list_practices.query import ListPractices, PracticeStatusFilter


class PracticeSummaryDTO(BaseModel):
    """One practice in a paginated list."""

    practice_id: UUID
    name: str = Field(..., max_length=PRACTICE_NAME_MAX_LENGTH)
    method_id: UUID
    site_id: UUID
    status: PracticeStatusFilter
    version_tag: str | None = Field(default=None, max_length=PRACTICE_VERSION_TAG_MAX_LENGTH)
    created_at: datetime


class PracticeListResponse(BaseModel):
    """Page of practices plus opaque next-page cursor."""

    items: list[PracticeSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.list_practices
    return handler


router = APIRouter(tags=["recipe"])


@router.get(
    "/practices",
    status_code=status.HTTP_200_OK,
    response_model=PracticeListResponse,
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
    summary="List practices with cursor pagination + status/method_id filters",
)
async def list_practices(
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
        PracticeStatusFilter | None,
        Query(
            alias="status",
            description="Optional status filter (Defined / Versioned / Deprecated).",
        ),
    ] = None,
    method_id: Annotated[
        UUID | None,
        Query(description="Optional Method-id filter."),
    ] = None,
) -> PracticeListResponse:
    page = await handler(
        ListPractices(
            cursor=cursor,
            limit=limit,
            status=status_filter,
            method_id=method_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
    )
    return PracticeListResponse(
        items=[
            PracticeSummaryDTO(
                practice_id=item.practice_id,
                name=item.name,
                method_id=item.method_id,
                site_id=item.site_id,
                status=item.status,  # type: ignore[arg-type]
                version_tag=item.version_tag,
                created_at=item.created_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
