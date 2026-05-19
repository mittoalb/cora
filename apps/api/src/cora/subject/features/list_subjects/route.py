"""HTTP route for the `list_subjects` query slice.

`GET /subjects?cursor=...&limit=50&status=Mounted` returns
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
from cora.subject.aggregates.subject import SUBJECT_NAME_MAX_LENGTH
from cora.subject.features.list_subjects.handler import Handler
from cora.subject.features.list_subjects.query import ListSubjects, SubjectStatusFilter


class SubjectSummaryDTO(BaseModel):
    """One subject in a paginated list."""

    subject_id: UUID
    name: str = Field(..., max_length=SUBJECT_NAME_MAX_LENGTH)
    status: SubjectStatusFilter
    created_at: datetime


class SubjectListResponse(BaseModel):
    """Page of subjects plus opaque next-page cursor."""

    items: list[SubjectSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.subject.list_subjects
    return handler


router = APIRouter(tags=["subject"])


@router.get(
    "/subjects",
    status_code=status.HTTP_200_OK,
    response_model=SubjectListResponse,
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
    summary="List subjects with cursor pagination",
)
async def list_subjects(
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
        SubjectStatusFilter | None,
        Query(
            alias="status",
            description=(
                "Optional status filter (one of: Received, Mounted, "
                "Measured, Removed, Returned, Stored, Discarded). "
                "Omit to return all statuses."
            ),
        ),
    ] = None,
) -> SubjectListResponse:
    page = await handler(
        ListSubjects(cursor=cursor, limit=limit, status=status_filter),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return SubjectListResponse(
        items=[
            SubjectSummaryDTO(
                subject_id=item.subject_id,
                name=item.name,
                status=item.status,  # type: ignore[arg-type]  # CHECK constraint guarantees enum membership
                created_at=item.created_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
