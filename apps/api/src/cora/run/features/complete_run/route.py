"""HTTP route for the `complete_run` slice.

Action endpoint at `POST /runs/{run_id}/complete`. No body. 204
No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.run.features.complete_run.command import CompleteRun
from cora.run.features.complete_run.handler import Handler


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.run.complete_run
    return handler


router = APIRouter(tags=["run"])


@router.post(
    "/runs/{run_id}/complete",
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
                "Run is not in `Running` status (complete requires `Running` "
                "today; re-completing a `Completed` run raises, completing an "
                "`Aborted` run raises), OR a concurrent write to the same run "
                "stream conflicted (optimistic concurrency)."
            ),
        },
    },
    summary="Mark an existing Run as completed (happy-path terminal)",
)
async def post_runs_complete(
    run_id: Annotated[UUID, Path(description="Target run's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        CompleteRun(run_id=run_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
