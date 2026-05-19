"""HTTP route for the `get_calibration` query slice.

`GET /calibrations/{calibration_id}` returns 200 + `CalibrationResponse`
on hit, 404 on miss.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.calibration._calibration_dtos import (
    SourceAssertedDTO,
    SourceComputedDTO,
    SourceMeasuredDTO,
    dto_from_source,
)
from cora.calibration.aggregates.calibration import (
    Calibration,
    CalibrationRevision,
    CalibrationStatus,
)
from cora.calibration.features.get_calibration.handler import Handler
from cora.calibration.features.get_calibration.query import GetCalibration
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class RevisionResponse(BaseModel):
    """Read-side DTO for one CalibrationRevision."""

    revision_id: UUID
    value: dict[str, Any]
    status: CalibrationStatus
    source: SourceMeasuredDTO | SourceComputedDTO | SourceAssertedDTO = Field(
        ...,
        discriminator="kind",
        description=(
            "Tagged source provenance — {kind, procedure_id|dataset_id|"
            "actor_id}. The wire envelope mirrors Caution / Safety "
            "polymorphic conventions; in-aggregate the source is a "
            "tagged-union VO and on the event payload it's exclusive-arc "
            "fields (Q5 lock)."
        ),
    )
    established_at: datetime
    established_by_actor_id: UUID
    decided_by_decision_id: UUID | None = None
    supersedes_revision_id: UUID | None = None


class CalibrationResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives + the polymorphic-source wire shape. Decouples
    the wire format from the domain model so the two can evolve
    independently.
    """

    id: UUID
    subsystem_or_asset_id: UUID
    quantity: str
    operating_point: dict[str, Any]
    description: str | None
    revisions: list[RevisionResponse]
    defined_at: datetime
    last_revised_at: datetime
    defined_by_actor_id: UUID


def _revision_response_from_state(revision: CalibrationRevision) -> RevisionResponse:
    return RevisionResponse(
        revision_id=revision.revision_id,
        value=revision.value,
        status=revision.status,
        source=dto_from_source(revision.source),
        established_at=revision.established_at,
        established_by_actor_id=revision.established_by_actor_id,
        decided_by_decision_id=revision.decided_by_decision_id,
        supersedes_revision_id=revision.supersedes_revision_id,
    )


def _response_from_state(calibration: Calibration) -> CalibrationResponse:
    return CalibrationResponse(
        id=calibration.id,
        subsystem_or_asset_id=calibration.subsystem_or_asset_id,
        quantity=calibration.quantity,
        operating_point=calibration.operating_point,
        description=calibration.description,
        revisions=[_revision_response_from_state(r) for r in calibration.revisions],
        defined_at=calibration.defined_at,
        last_revised_at=calibration.last_revised_at,
        defined_by_actor_id=calibration.defined_by_actor_id,
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.calibration.get_calibration
    return handler


router = APIRouter(tags=["calibration"])


@router.get(
    "/calibrations/{calibration_id}",
    status_code=status.HTTP_200_OK,
    response_model=CalibrationResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No calibration exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a calibration by id",
)
async def get_calibrations(
    calibration_id: Annotated[UUID, Path(description="Target calibration's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> CalibrationResponse:
    calibration = await handler(
        GetCalibration(calibration_id=calibration_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if calibration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calibration {calibration_id} not found",
        )
    return _response_from_state(calibration)
