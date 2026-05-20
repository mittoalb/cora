"""HTTP route for the `list_datasets` query slice.

`GET /datasets?cursor=...&status=Registered&producing_run_id=<uuid>&subject_id=<uuid>`
returns `{"items": [...], "next_cursor": "..." | null}`.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from cora.data.aggregates.dataset import (
    DATASET_NAME_MAX_LENGTH,
    DATASET_URI_MAX_LENGTH,
)
from cora.data.features.list_datasets.handler import Handler
from cora.data.features.list_datasets.query import DatasetStatusFilter, ListDatasets
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class DatasetSummaryDTO(BaseModel):
    """One dataset in a paginated list."""

    dataset_id: UUID
    name: str = Field(..., max_length=DATASET_NAME_MAX_LENGTH)
    uri: str = Field(..., max_length=DATASET_URI_MAX_LENGTH)
    producing_run_id: UUID | None
    subject_id: UUID | None
    status: DatasetStatusFilter
    created_at: datetime


class DatasetListResponse(BaseModel):
    """Page of datasets plus opaque next-page cursor."""

    items: list[DatasetSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.data.list_datasets
    return handler


router = APIRouter(tags=["data"])


@router.get(
    "/datasets",
    status_code=status.HTTP_200_OK,
    response_model=DatasetListResponse,
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
    summary="List datasets with cursor pagination + status/run/subject filters",
)
async def list_datasets(
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
        DatasetStatusFilter | None,
        Query(
            alias="status",
            description="Optional status filter (Registered / Discarded).",
        ),
    ] = None,
    producing_run_id: Annotated[
        UUID | None,
        Query(description="Optional Run-id filter."),
    ] = None,
    subject_id: Annotated[
        UUID | None,
        Query(description="Optional Subject-id filter."),
    ] = None,
) -> DatasetListResponse:
    page = await handler(
        ListDatasets(
            cursor=cursor,
            limit=limit,
            status=status_filter,
            producing_run_id=producing_run_id,
            subject_id=subject_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return DatasetListResponse(
        items=[
            DatasetSummaryDTO(
                dataset_id=item.dataset_id,
                name=item.name,
                uri=item.uri,
                producing_run_id=item.producing_run_id,
                subject_id=item.subject_id,
                status=item.status,
                created_at=item.created_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
