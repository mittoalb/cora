"""HTTP route for the `list_plans` query slice.

`GET /plans?cursor=...&limit=50&status=Versioned&practice_id=<uuid>`
returns `{"items": [...], "next_cursor": "..." | null}`.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.recipe.aggregates.plan import (
    PLAN_NAME_MAX_LENGTH,
    PLAN_VERSION_TAG_MAX_LENGTH,
)
from cora.recipe.features.list_plans.handler import Handler
from cora.recipe.features.list_plans.query import ListPlans, PlanStatusFilter


class PlanSummaryDTO(BaseModel):
    """One plan in a paginated list."""

    plan_id: UUID
    name: str = Field(..., max_length=PLAN_NAME_MAX_LENGTH)
    practice_id: UUID
    method_id: UUID
    status: PlanStatusFilter
    version_tag: str | None = Field(default=None, max_length=PLAN_VERSION_TAG_MAX_LENGTH)
    created_at: datetime


class PlanListResponse(BaseModel):
    """Page of plans plus opaque next-page cursor."""

    items: list[PlanSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.list_plans
    return handler


router = APIRouter(tags=["recipe"])


@router.get(
    "/plans",
    status_code=status.HTTP_200_OK,
    response_model=PlanListResponse,
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
    summary="List plans with cursor pagination + status/practice_id filters",
)
async def list_plans(
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
        PlanStatusFilter | None,
        Query(
            alias="status",
            description="Optional status filter (Defined / Versioned / Deprecated).",
        ),
    ] = None,
    practice_id: Annotated[
        UUID | None,
        Query(description="Optional Practice-id filter."),
    ] = None,
) -> PlanListResponse:
    page = await handler(
        ListPlans(
            cursor=cursor,
            limit=limit,
            status=status_filter,
            practice_id=practice_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
    )
    return PlanListResponse(
        items=[
            PlanSummaryDTO(
                plan_id=item.plan_id,
                name=item.name,
                practice_id=item.practice_id,
                method_id=item.method_id,
                status=item.status,  # type: ignore[arg-type]
                version_tag=item.version_tag,
                created_at=item.created_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
