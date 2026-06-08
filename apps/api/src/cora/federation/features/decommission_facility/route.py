"""HTTP route for the `decommission_facility` slice.

Action endpoint at `POST /federation/facilities/{facility_id}/decommission`.
Optional JSON body with a free-text `reason` field; 204 No Content on
success. Mirrors `revoke_credential` (lifecycle-state transitions sit
under the resource via verb, not as a DELETE, so the audit gesture is
distinguishable from a resource-delete semantic).

The optional `reason` body field flows through to the emitted
`FacilityDecommissioned` event payload so operator context survives
on the immutable event log.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.features.decommission_facility.command import DecommissionFacility
from cora.federation.features.decommission_facility.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class DecommissionFacilityBody(BaseModel):
    """Optional decommission-facility request body."""

    reason: str | None = Field(
        default=None,
        description=(
            "Optional operator-supplied reason for decommissioning the "
            "facility (audit-log breadcrumb). Flows onto the "
            "FacilityDecommissioned event payload."
        ),
    )

    model_config = {"extra": "forbid"}


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.decommission_facility
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/facilities/{facility_id}/decommission",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No facility exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Facility is already Decommissioned (decommission_facility "
                "is strict-not-idempotent; Decommissioned is terminal). The "
                "code stays reserved even after decommissioning; "
                "re-registering with the same code is forbidden."
            ),
        },
    },
    summary="Decommission a Facility (terminal: Active -> Decommissioned)",
)
async def post_federation_facilities_decommission(
    facility_id: Annotated[UUID, Path(description="Target facility's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    body: DecommissionFacilityBody | None = None,
) -> None:
    await handler(
        DecommissionFacility(
            facility_id=FacilityId(facility_id),
            reason=body.reason if body is not None else None,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
