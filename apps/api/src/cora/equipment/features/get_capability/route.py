"""HTTP route for the `get_capability` query slice.

`GET /capabilities/{capability_id}` returns 200 + CapabilityResponse
on hit, 404 on miss. The handler returns `Capability | None`; the
route maps None to 404 via HTTPException (idiomatic in routes; the
BC's exception-handler infrastructure stays focused on domain /
application errors raised deeper in the stack).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.capability import CAPABILITY_NAME_MAX_LENGTH
from cora.equipment.features.get_capability.handler import Handler
from cora.equipment.features.get_capability.query import GetCapability
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


class CapabilityResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. Decouples the wire format
    from the domain model so the two can evolve independently.
    `status` is the StrEnum's string value (Defined / Versioned /
    Deprecated). `current_version` is the operator-supplied label
    of the most recent version_capability call (null until first
    version).
    """

    id: UUID
    name: str = Field(..., max_length=CAPABILITY_NAME_MAX_LENGTH)
    status: str
    current_version: str | None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.get_capability
    return handler


router = APIRouter(tags=["equipment"])


@router.get(
    "/capabilities/{capability_id}",
    status_code=status.HTTP_200_OK,
    response_model=CapabilityResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No capability exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a capability by id",
)
async def get_capabilities(
    capability_id: Annotated[UUID, Path(description="Target capability's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> CapabilityResponse:
    capability = await handler(
        GetCapability(capability_id=capability_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
    if capability is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Capability {capability_id} not found",
        )
    return CapabilityResponse(
        id=capability.id,
        name=capability.name.value,
        status=capability.status.value,
        current_version=capability.current_version,
    )
