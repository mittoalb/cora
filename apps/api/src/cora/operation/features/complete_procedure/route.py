"""HTTP route for the `complete_procedure` slice.

Action endpoint at `POST /procedures/{procedure_id}/complete`. No
body. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.operation.features.complete_procedure.command import CompleteProcedure
from cora.operation.features.complete_procedure.handler import Handler


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.complete_procedure
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/complete",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No procedure exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Procedure is not in `Running` status (complete requires "
                "`Running` today; re-completing a `Completed` procedure raises, "
                "completing an `Aborted` procedure raises), OR a concurrent "
                "write to the same procedure stream conflicted (optimistic "
                "concurrency)."
            ),
        },
    },
    summary="Mark an existing Procedure as completed (happy-path terminal)",
)
async def post_procedures_complete(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        CompleteProcedure(procedure_id=procedure_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
