"""HTTP route for the `get_run` query slice.

`GET /runs/{run_id}` returns 200 + RunResponse on hit, 404 on miss.

Response shape: `{id, name, plan_id, subject_id, status}`.
`subject_id` is null for calibration / dark-field runs.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.run.aggregates.run import RUN_NAME_MAX_LENGTH
from cora.run.features.get_run.handler import Handler
from cora.run.features.get_run.query import GetRun


class RunResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. `status` is the StrEnum's
    string value (Running at 6f-1; transitions add more in 6f-2+).
    `subject_id` is null for calibration / dark-field runs.
    """

    id: UUID
    name: str = Field(..., max_length=RUN_NAME_MAX_LENGTH)
    plan_id: UUID
    subject_id: UUID | None
    status: str


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
) -> RunResponse:
    run = await handler(
        GetRun(run_id=run_id),
        principal_id=principal_id,
        correlation_id=cid,
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
        status=run.status.value,
    )
