"""HTTP route for the `start_procedure` slice.

Action endpoint at `POST /procedures/{procedure_id}/start`. No body.
204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.operation.features.start_procedure.command import StartProcedure
from cora.operation.features.start_procedure.handler import Handler


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.start_procedure
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/start",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "No procedure exists with the given id, OR a target Asset "
                "referenced by the procedure no longer exists."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Procedure is not in `Defined` status (start requires "
                "`Defined`; re-starting a `Running` procedure raises, "
                "starting any terminal raises), OR a target Asset is "
                "Decommissioned, OR a concurrent write to the same procedure "
                "stream conflicted (optimistic concurrency)."
            ),
        },
    },
    summary="Transition an existing Procedure from Defined to Running",
)
async def post_procedures_start(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        StartProcedure(procedure_id=procedure_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
