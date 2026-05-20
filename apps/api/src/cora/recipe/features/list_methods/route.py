"""HTTP route for the `list_methods` query slice.

`GET /methods?cursor=...&limit=50&status=Versioned` returns
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
from cora.recipe.aggregates.method import (
    METHOD_NAME_MAX_LENGTH,
    METHOD_VERSION_TAG_MAX_LENGTH,
)
from cora.recipe.features.list_methods.handler import Handler
from cora.recipe.features.list_methods.query import ListMethods, MethodStatusFilter


class MethodSummaryDTO(BaseModel):
    """One method in a paginated list."""

    method_id: UUID
    name: str = Field(..., max_length=METHOD_NAME_MAX_LENGTH)
    status: MethodStatusFilter
    version_tag: str | None = Field(default=None, max_length=METHOD_VERSION_TAG_MAX_LENGTH)
    created_at: datetime
    parameters_schema_present: bool = Field(
        default=False,
        description=(
            "True iff the most recent `MethodParametersSchemaUpdated` event "
            "for this Method carried a non-NULL parameters_schema (Phase "
            "6g-a). The schema content itself is loaded on demand."
        ),
    )


class MethodListResponse(BaseModel):
    """Page of methods plus opaque next-page cursor."""

    items: list[MethodSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.list_methods
    return handler


router = APIRouter(tags=["recipe"])


@router.get(
    "/methods",
    status_code=status.HTTP_200_OK,
    response_model=MethodListResponse,
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
    summary="List methods with cursor pagination + status filter",
)
async def list_methods(
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
        MethodStatusFilter | None,
        Query(
            alias="status",
            description=(
                "Optional status filter (one of: Defined, Versioned, "
                "Deprecated). Omit to return all statuses."
            ),
        ),
    ] = None,
) -> MethodListResponse:
    page = await handler(
        ListMethods(cursor=cursor, limit=limit, status=status_filter),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return MethodListResponse(
        items=[
            MethodSummaryDTO(
                method_id=item.method_id,
                name=item.name,
                status=item.status,
                version_tag=item.version_tag,
                created_at=item.created_at,
                parameters_schema_present=item.parameters_schema_present,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
