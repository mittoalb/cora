"""HTTP route for the `list_calibrations` query slice.

`GET /calibrations` accepts these optional query params: `cursor`,
`limit`, `subsystem_or_asset_id`, `quantity`,
`latest_revision_status` (one or more; multi-value),
`latest_revision_source_kind` (one or more; multi-value).

No default filter: operators commonly want to see all calibrations
for an asset including provisional + verified across all source
kinds. UX defaults can be added in 12a-3+ if pilot use surfaces a
common-case shortcut (per the `cora.infrastructure.list_query`
growth-rule discipline).
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from cora.calibration.features.list_calibrations.handler import Handler
from cora.calibration.features.list_calibrations.query import (
    CalibrationSourceKindFilter,
    CalibrationStatusFilter,
    ListCalibrations,
)
from cora.calibration.quantities import CalibrationQuantity
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class CalibrationSummaryDTO(BaseModel):
    """One calibration in a paginated list."""

    calibration_id: UUID
    subsystem_or_asset_id: UUID
    quantity: str
    operating_point: dict[str, Any]
    description: str | None = None
    defined_at: datetime
    last_revised_at: datetime
    defined_by_actor_id: UUID
    revision_count: int = Field(..., ge=0)
    latest_revision_status: str | None = None
    latest_revision_source_kind: str | None = None


class CalibrationListPageResponse(BaseModel):
    """Page of calibration summaries plus opaque next-page cursor."""

    items: list[CalibrationSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.calibration.list_calibrations
    return handler


router = APIRouter(tags=["calibration"])


@router.get(
    "/calibrations",
    status_code=status.HTTP_200_OK,
    response_model=CalibrationListPageResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": ("Query parameters failed validation OR `cursor` was malformed."),
        },
    },
    summary=(
        "List calibrations with cursor pagination + subsystem / quantity / "
        "latest-revision-status / latest-revision-source-kind filters."
    ),
)
async def list_calibrations(
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
    subsystem_or_asset_id: Annotated[
        UUID | None,
        Query(description="Optional scope: only calibrations OF this Asset/subsystem."),
    ] = None,
    quantity: Annotated[
        CalibrationQuantity | None,
        Query(description="Optional quantity filter (closed CalibrationQuantity enum)."),
    ] = None,
    latest_revision_status: Annotated[
        list[CalibrationStatusFilter] | None,
        Query(
            description=(
                "Optional filter on the latest-revision's status; multi-value. "
                "Pass once for a single value, repeat for any-of."
            ),
        ),
    ] = None,
    latest_revision_source_kind: Annotated[
        list[CalibrationSourceKindFilter] | None,
        Query(
            description=(
                "Optional filter on the latest-revision's source kind "
                "(measured / computed / asserted); multi-value."
            ),
        ),
    ] = None,
) -> CalibrationListPageResponse:
    page = await handler(
        ListCalibrations(
            cursor=cursor,
            limit=limit,
            subsystem_or_asset_id=subsystem_or_asset_id,
            quantity=quantity.value if quantity is not None else None,
            latest_revision_statuses=latest_revision_status,
            latest_revision_source_kinds=latest_revision_source_kind,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return CalibrationListPageResponse(
        items=[
            CalibrationSummaryDTO(
                calibration_id=item.calibration_id,
                subsystem_or_asset_id=item.subsystem_or_asset_id,
                quantity=item.quantity,
                operating_point=item.operating_point,
                description=item.description,
                defined_at=item.defined_at,
                last_revised_at=item.last_revised_at,
                defined_by_actor_id=item.defined_by_actor_id,
                revision_count=item.revision_count,
                latest_revision_status=item.latest_revision_status,
                latest_revision_source_kind=item.latest_revision_source_kind,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )


__all__ = ["CalibrationListPageResponse", "CalibrationSummaryDTO", "router"]
