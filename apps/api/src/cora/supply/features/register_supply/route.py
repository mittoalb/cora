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
from cora.shared.facility_code import FACILITY_CODE_MAX_LENGTH
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
            "(for example '2-BM LN2 drop', 'APS storage-ring beam', 'central N2 supply')."
        ),
    )
    facility_code: str = Field(
        ...,
        min_length=1,
        max_length=FACILITY_CODE_MAX_LENGTH,
        pattern=r"^[a-z0-9-]{1,32}$",
        description=(
            "Cross-deployment convergent slug of the Facility owning this Supply "
            "(for example 'aps', 'maxiv', 'esrf'). Lowercase ASCII alphanumeric "
            "plus dash, 1-32 chars. The handler resolves the slug via the Federation "
            "BC's facility projection; unknown codes are rejected with HTTP 404."
        ),
    )
    containing_asset_id: UUID | None = Field(
        default=None,
        description=(
            "Optional physical-equipment containment back-reference. Omit (or pass "
            "null) for facility-scope resources (storage-ring beam, central LN2 plant). "
            "Set to the id of an existing Asset in the Equipment BC hierarchy for "
            "sector / beamline / unit scoped resources (per "
            "project_supply_sector_disposition Option A). The handler resolves the id "
            "via the Equipment BC's Asset projection; unknown ids are rejected with "
            "HTTP 404. Decommissioned-Asset binding is allowed (mirrors slice 6A "
            "FacilityParentNotFoundError precedent)."
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
            "description": (
                "Domain invariant violated (for example whitespace-only kind or name)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "Either `facility_code` does not resolve to a Facility row in the "
                "Federation projection, OR `containing_asset_id` does not resolve to "
                "an Asset row in the Equipment projection. Operator remedies: "
                "register the missing parent first (`POST /federation/facilities` or "
                "`POST /assets`), or correct the id / slug on the Supply registration."
            ),
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
                "invalid scope enum, length out of bounds, facility_code regex "
                "violation), OR Idempotency-Key was reused with a different "
                "request body."
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
        RegisterSupply(
            scope=body.scope,
            kind=body.kind,
            name=body.name,
            facility_code=body.facility_code,
            containing_asset_id=body.containing_asset_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterSupplyResponse(supply_id=supply_id)
