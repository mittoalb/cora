"""HTTP route for the `get_run` query slice.

`GET /runs/{run_id}` returns 200 + RunResponse on hit, 404 on miss.

Response shape: `{id, name, plan_id, subject_id, raid, status}`.
`subject_id` and `raid` are null when not set (calibration runs, or
Runs not registered against a research activity respectively).
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.run.aggregates.run import RUN_NAME_MAX_LENGTH
from cora.run.features.get_run.handler import Handler
from cora.run.features.get_run.query import GetRun


class RunResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. `status` is the StrEnum's
    string value. `subject_id` is null for calibration / dark-field
    runs. `raid` is null when no Research Activity Identifier was
    supplied at start time (additive retrofit).

    `override_parameters` and `effective_parameters` carry the
    parameter set: overrides the operator supplied at start
    time, and the resolved merge of Plan defaults + overrides that
    actually governed this Run. Both default `{}`. `triggered_by`
    captures what initiated the Run (None if unrecorded).

    `campaign_id` (6i-c) is the Campaign this Run is a member of, set
    either at start time (StartRun.campaign_id) or post-hoc via
    add_run_to_campaign. None when the Run is standalone (not part of
    any Campaign). Closes design-memo Watch #17 (per Caution-design
    cross-BC consistency precedent).
    """

    id: UUID
    name: str = Field(..., max_length=RUN_NAME_MAX_LENGTH)
    plan_id: UUID
    subject_id: UUID | None
    raid: str | None
    status: str
    override_parameters: dict[str, Any] = Field(default_factory=dict)
    effective_parameters: dict[str, Any] = Field(default_factory=dict)
    triggered_by: str | None = None
    campaign_id: UUID | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.run.get_run
    return handler


router = APIRouter(tags=["run"])


@router.get(
    "/runs/{run_id}",
    status_code=status.HTTP_200_OK,
    response_model=RunResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No run exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a run by id",
)
async def get_runs(
    run_id: Annotated[UUID, Path(description="Target run's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> RunResponse:
    run = await handler(
        GetRun(run_id=run_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )
    return RunResponse(
        id=run.id,
        name=run.name.value,
        plan_id=run.plan_id,
        subject_id=run.subject_id,
        raid=run.raid,
        status=run.status.value,
        override_parameters=run.override_parameters,
        effective_parameters=run.effective_parameters,
        triggered_by=run.triggered_by,
        campaign_id=run.campaign_id,
    )
