"""HTTP route for the `list_permits` query slice.

`GET /federation/permits` accepts these optional query params:
`cursor`, `limit`, `direction`, `status`, `peer_facility_code`.
Returns `{"items": [...], "next_cursor": "..." | null}`.

Per-arc terms detail (read_scope / scopes /
accepted_canonicalization_versions / etc.) is NOT surfaced here;
fetch by id via `get_permit` for the full polymorphic terms VO.
The list response surfaces only `terms_kind` plus the cross-
direction shared scope sets.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from cora.federation.aggregates.permit import AbiTier, Direction, PermitStatus
from cora.federation.features.list_permits.handler import Handler
from cora.federation.features.list_permits.query import (
    ListPermits,
    PermitDirectionFilter,
    PermitStatusFilter,
)
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class PermitSummaryDTO(BaseModel):
    """One permit in a paginated list."""

    permit_id: UUID
    peer_facility_code: str = Field(..., min_length=1)
    direction: Direction
    allowed_credential_ids: list[UUID] = Field(default_factory=list[UUID])
    allowed_payload_types: list[str] = Field(default_factory=list[str])
    allowed_artifact_kinds: list[str] = Field(default_factory=list[str])
    abi_tier_floor: AbiTier
    expires_at: datetime
    defined_by: UUID
    status: PermitStatus
    terms_kind: Direction
    defined_at: datetime
    activated_at: datetime | None = None
    suspended_at: datetime | None = None
    resumed_at: datetime | None = None
    revoked_at: datetime | None = None


class PermitListResponse(BaseModel):
    """Page of permits plus opaque next-page cursor."""

    items: list[PermitSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.list_permits
    return handler


router = APIRouter(tags=["federation"])


@router.get(
    "/federation/permits",
    status_code=status.HTTP_200_OK,
    response_model=PermitListResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Query parameters failed validation OR `cursor` was malformed.",
        },
    },
    summary=(
        "List federation Permits with cursor pagination + direction / status / "
        "peer_facility_code filters. Per-arc terms detail not surfaced (fetch "
        "get_permit for the full polymorphic terms VO)."
    ),
)
async def list_permits(
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
    direction: Annotated[
        PermitDirectionFilter | None,
        Query(description="Optional direction filter (Outbound | Inbound)."),
    ] = None,
    status_filter: Annotated[
        PermitStatusFilter | None,
        Query(
            alias="status",
            description=(
                "Optional status filter (one of the 4 PermitStatus values: "
                "Defined / Active / Suspended / Revoked)."
            ),
        ),
    ] = None,
    peer_facility_code: Annotated[
        str | None,
        Query(
            description=(
                "Optional peer-facility-code filter; matches the "
                "FacilityCode string of the peer facility."
            ),
        ),
    ] = None,
) -> PermitListResponse:
    page = await handler(
        ListPermits(
            cursor=cursor,
            limit=limit,
            direction=direction,
            status=status_filter,
            peer_facility_code=peer_facility_code,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return PermitListResponse(
        items=[
            PermitSummaryDTO(
                permit_id=item.permit_id,
                peer_facility_code=item.peer_facility_code,
                direction=Direction(item.direction),
                allowed_credential_ids=[UUID(str(c)) for c in item.allowed_credential_ids],
                allowed_payload_types=[str(p) for p in item.allowed_payload_types],
                allowed_artifact_kinds=[str(k) for k in item.allowed_artifact_kinds],
                abi_tier_floor=AbiTier(item.abi_tier_floor),
                expires_at=item.expires_at,
                defined_by=item.defined_by,
                status=PermitStatus(item.status),
                terms_kind=Direction(item.terms_kind),
                defined_at=item.defined_at,
                activated_at=item.activated_at,
                suspended_at=item.suspended_at,
                resumed_at=item.resumed_at,
                revoked_at=item.revoked_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )


__all__ = ["PermitListResponse", "PermitSummaryDTO", "router"]
