"""HTTP route for the `hold_run` slice.

Action endpoint at `POST /runs/{run_id}/hold`. No body. 204
No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.run.features.hold_run.command import HoldRun
from cora.run.features.hold_run.handler import Handler


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.run.hold_run
    return handler


router = APIRouter(tags=["run"])


@router.post(
    "/runs/{run_id}/hold",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No run exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Run is not in `Running` status (hold requires `Running`; "
                "re-holding a `Held` run raises, holding a terminal run "
                "raises), OR a concurrent write to the same run stream "
                "conflicted (optimistic concurrency)."
            ),
        },
    },
    summary="Pause an actively-running Run (Running → Held)",
)
async def post_runs_hold(
    run_id: Annotated[UUID, Path(description="Target run's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        HoldRun(run_id=run_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
