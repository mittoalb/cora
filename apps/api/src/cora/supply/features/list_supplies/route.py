"""HTTP route for the `list_supplies` query slice.

`GET /supplies?cursor=...&limit=50&scope=Beamline&kind=LiquidNitrogen&status=Available`
returns `{"items": [...], "next_cursor": "..." | null}`.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.supply.aggregates.supply import (
    SUPPLY_KIND_MAX_LENGTH,
    SUPPLY_NAME_MAX_LENGTH,
    SUPPLY_REASON_MAX_LENGTH,
    SupplyScope,
    SupplyStatus,
    TriggerSource,
)
from cora.supply.features.list_supplies.handler import Handler
from cora.supply.features.list_supplies.query import (
    ListSupplies,
    SupplyScopeFilter,
    SupplyStatusFilter,
)


class SupplySummaryDTO(BaseModel):
    """One supply in a paginated list."""

    supply_id: UUID
    scope: SupplyScope
    kind: str = Field(..., max_length=SUPPLY_KIND_MAX_LENGTH)
    name: str = Field(..., max_length=SUPPLY_NAME_MAX_LENGTH)
    status: SupplyStatus
    registered_at: datetime
    last_status_changed_at: datetime | None = None
    last_status_reason: str | None = Field(default=None, max_length=SUPPLY_REASON_MAX_LENGTH)
    last_trigger: TriggerSource | None = None


class SupplyListResponse(BaseModel):
    """Page of supplies plus opaque next-page cursor."""

    items: list[SupplySummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.supply.list_supplies
    return handler


router = APIRouter(tags=["supply"])


@router.get(
    "/supplies",
    status_code=status.HTTP_200_OK,
    response_model=SupplyListResponse,
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
    summary="List supplies with cursor pagination + scope/kind/status filters",
)
async def list_supplies(
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
    scope: Annotated[
        SupplyScopeFilter | None,
        Query(
            description=(
                "Optional scope filter (one of: Facility, Sector, Beamline). "
                "Omit to return all scopes."
            ),
        ),
    ] = None,
    kind: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=SUPPLY_KIND_MAX_LENGTH,
            description=(
                "Optional kind filter (free-form, exact match; e.g. "
                "'LiquidNitrogen'). Omit to return all kinds."
            ),
        ),
    ] = None,
    status_filter: Annotated[
        SupplyStatusFilter | None,
        Query(
            alias="status",
            description=(
                "Optional status filter (one of: Unknown, Available, Degraded, "
                "Unavailable, Recovering). Omit to return all statuses."
            ),
        ),
    ] = None,
) -> SupplyListResponse:
    page = await handler(
        ListSupplies(
            cursor=cursor,
            limit=limit,
            scope=scope,
            kind=kind,
            status=status_filter,
        ),
        principal_id=principal_id,
        correlation_id=cid,
    )
    return SupplyListResponse(
        items=[
            SupplySummaryDTO(
                supply_id=item.supply_id,
                scope=SupplyScope(item.scope),
                kind=item.kind,
                name=item.name,
                status=SupplyStatus(item.status),
                registered_at=item.registered_at,
                last_status_changed_at=item.last_status_changed_at,
                last_status_reason=item.last_status_reason,
                last_trigger=(
                    TriggerSource(item.last_trigger) if item.last_trigger is not None else None
                ),
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
