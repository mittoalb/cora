"""HTTP route for the `define_calibration` slice.

Pydantic request/response schemas + APIRouter for `POST /calibrations`.
The BC-level wiring (`cora.calibration.routes.register_calibration_routes`)
includes this router on the FastAPI app.

`operating_point` is a free dict at the wire layer; STRICT JSON Schema
validation against the quantity's registered schema happens at the
decider. Misses surface as HTTP 400 via the exception handler.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.calibration.aggregates.calibration import CALIBRATION_DESCRIPTION_MAX_LENGTH
from cora.calibration.features.define_calibration.command import DefineCalibration
from cora.calibration.features.define_calibration.handler import IdempotentHandler
from cora.calibration.quantities import CalibrationQuantity
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class DefineCalibrationRequest(BaseModel):
    """Body for `POST /calibrations`."""

    subsystem_or_asset_id: UUID = Field(
        ...,
        description=(
            "What this calibration is OF (typically the Asset id whose "
            "behavior is being measured — for example, the rotary stage "
            "whose rotation-axis center is being tracked). Bare UUID "
            "reference; existence NOT verified at the write path per "
            "the cross-BC eventual-consistency stance."
        ),
    )
    quantity: CalibrationQuantity = Field(
        ...,
        description=(
            "The physical quantity being calibrated. Closed catalog at "
            "`cora.calibration.quantities`; each value has registered "
            "operating_point + value JSON Schemas. Adding a quantity = "
            "PR. Phase 12a-2 ships: rotation_center, detector_pixel_size."
        ),
    )
    operating_point: dict[str, Any] = Field(
        ...,
        description=(
            "JSON-shaped dict describing the operating regime "
            "(energy_keV, optics_config, etc.). Validated STRICT against "
            "the quantity's operating_point_schema "
            "(`additionalProperties: False`; primitive types only). "
            "Identity-tuple uniqueness "
            "`(subsystem_or_asset_id, quantity, operating_point)` "
            "enforced via Postgres jsonb UNIQUE on the projection (Q6 "
            "lock: key-order normalized + numeric value-equality "
            "`25 == 25.0`)."
        ),
    )
    description: str | None = Field(
        default=None,
        max_length=CALIBRATION_DESCRIPTION_MAX_LENGTH,
        description=(
            "Optional operator-prose notes (0-2000 chars after trim). "
            "Empty / whitespace-only collapses to None at the slice "
            "boundary. Matches Method/Plan/Family description "
            "precedent."
        ),
    )


class DefineCalibrationResponse(BaseModel):
    """Response body for `POST /calibrations`."""

    calibration_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.calibration.define_calibration
    return handler


router = APIRouter(tags=["calibration"])


@router.post(
    "/calibrations",
    status_code=status.HTTP_201_CREATED,
    response_model=DefineCalibrationResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: operating_point fails the "
                "quantity's operating_point_schema (missing required "
                "field, additional property, type mismatch), or "
                "description exceeds 2000 chars after trim."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Calibration with the same "
                "(subsystem_or_asset_id, quantity, operating_point) "
                "identity already exists (Postgres jsonb UNIQUE on "
                "proj_calibration_summary). Operators querying for an "
                "existing calibration should use GET /calibrations with "
                "the same identity filters instead."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (e.g. unknown "
                "CalibrationQuantity enum value) OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Define a new Calibration record",
)
async def post_calibrations(
    body: DefineCalibrationRequest,
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
                "response instead of writing a duplicate definition."
            ),
        ),
    ] = None,
) -> DefineCalibrationResponse:
    calibration_id = await handler(
        DefineCalibration(
            subsystem_or_asset_id=body.subsystem_or_asset_id,
            quantity=body.quantity,
            operating_point=body.operating_point,
            description=body.description,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return DefineCalibrationResponse(calibration_id=calibration_id)
