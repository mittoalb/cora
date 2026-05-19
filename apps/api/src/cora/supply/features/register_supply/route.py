"""HTTP route for the `register_supply` slice.

Pydantic request/response schemas + APIRouter for `POST /supplies`.
The slice's BC-level wiring (`cora.supply.routes.register_supply_routes`)
includes this router on the FastAPI app.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.supply.aggregates.supply import (
    SUPPLY_KIND_MAX_LENGTH,
    SUPPLY_NAME_MAX_LENGTH,
    SupplyScope,
)
from cora.supply.features.register_supply.command import RegisterSupply
from cora.supply.features.register_supply.handler import IdempotentHandler


class RegisterSupplyRequest(BaseModel):
    """Body for `POST /supplies`."""

    scope: SupplyScope = Field(
        ...,
        description=(
            "Hierarchical scope at which the supply is provisioned. "
            "Facility = facility-wide (storage-ring photon beam, central LN2 plant), "
            "Sector = ring sector / gas-manifold loop, "
            "Beamline = beamline-local (per-beamline drop)."
        ),
    )
    kind: str = Field(
        ...,
        min_length=1,
        max_length=SUPPLY_KIND_MAX_LENGTH,
        description=(
            "Free-form supply-kind discriminator (PhotonBeam, LiquidNitrogen, "
            "CompressedAir, ElectricalPower, Vacuum, ProcessGas, ComputePool, etc.). "
            "Documented starter vocabulary in project_supply_design memo; closed "
            "StrEnum promotion deferred until pilot vocabulary settles."
        ),
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=SUPPLY_NAME_MAX_LENGTH,
        description=(
            "Operator-readable display name for this Supply instance "
            "(e.g. '35-BM LN2 drop', 'APS storage-ring beam', 'central N2 supply')."
        ),
    )


class RegisterSupplyResponse(BaseModel):
    """Response body for `POST /supplies`."""

    supply_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.supply.register_supply
    return handler


router = APIRouter(tags=["supply"])


@router.post(
    "/supplies",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterSupplyResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": ("Domain invariant violated (e.g. whitespace-only kind or name)."),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Defensive guard: the target supply stream already has events. "
                "Essentially impossible in production with UUIDv7 ids; documented "
                "for OpenAPI completeness against the BC's exception handler."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing field, "
                "invalid scope enum, length out of bounds), OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Register a new continuously-available resource (lands in Unknown)",
)
async def post_supplies(
    body: RegisterSupplyRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied unique key per logical request. "
                "Retries with the same key + same body return the cached "
                "response instead of re-creating the supply."
            ),
        ),
    ] = None,
) -> RegisterSupplyResponse:
    supply_id = await handler(
        RegisterSupply(scope=body.scope, kind=body.kind, name=body.name),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterSupplyResponse(supply_id=supply_id)
