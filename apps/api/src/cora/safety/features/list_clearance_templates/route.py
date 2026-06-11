"""HTTP route for the `list_clearance_templates` query slice.

`GET /clearance-templates?cursor=...&limit=50&facility_code=aps&status=Active`
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
from cora.safety.aggregates.clearance_template import (
    CLEARANCE_TEMPLATE_CODE_MAX_LENGTH,
    CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH,
)
from cora.safety.features.list_clearance_templates.handler import Handler
from cora.safety.features.list_clearance_templates.query import (
    ClearanceTemplateStatusFilter,
    ListClearanceTemplates,
)


class ClearanceTemplateSummaryDTO(BaseModel):
    """One clearance template in a paginated list."""

    template_id: UUID
    code: str = Field(..., max_length=CLEARANCE_TEMPLATE_CODE_MAX_LENGTH)
    title: str = Field(..., max_length=CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH)
    facility_code: str
    version: int
    status: ClearanceTemplateStatusFilter
    defined_at: datetime


class ClearanceTemplateListResponse(BaseModel):
    """Page of clearance templates plus opaque next-page cursor."""

    items: list[ClearanceTemplateSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.safety.list_clearance_templates
    return handler


router = APIRouter(tags=["safety"])


@router.get(
    "/clearance-templates",
    status_code=status.HTTP_200_OK,
    response_model=ClearanceTemplateListResponse,
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
    summary="List clearance templates with cursor pagination + filters",
)
async def list_clearance_templates_endpoint(
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
    facility_code: Annotated[
        str | None,
        Query(
            description=(
                "Optional facility-code filter (exact match, "
                "e.g. 'aps', 'maxiv'). Omit to return all facilities."
            ),
        ),
    ] = None,
    status_filter: Annotated[
        ClearanceTemplateStatusFilter | None,
        Query(
            alias="status",
            description=(
                "Optional status filter (one of: Draft, Active, "
                "Deprecated, Withdrawn). Omit to return all statuses."
            ),
        ),
    ] = None,
    code: Annotated[
        str | None,
        Query(
            description=(
                "Optional code filter (exact match, e.g. 'ESAF', 'SAF'). Omit to return all codes."
            ),
        ),
    ] = None,
) -> ClearanceTemplateListResponse:
    page = await handler(
        ListClearanceTemplates(
            cursor=cursor,
            limit=limit,
            facility_code=facility_code,
            status=status_filter,
            code=code,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return ClearanceTemplateListResponse(
        items=[
            ClearanceTemplateSummaryDTO(
                template_id=item.template_id,
                code=item.code,
                title=item.title,
                facility_code=item.facility_code,
                version=item.version,
                status=item.status,
                defined_at=item.defined_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
