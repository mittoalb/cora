"""HTTP route for the `submit_clearance` slice.

Action endpoint at `POST /clearances/{clearance_id}/submit`. No body
fields. 204 No Content on success.
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
from cora.safety.features.submit_clearance.command import SubmitClearance
from cora.safety.features.submit_clearance.handler import Handler


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.safety.submit_clearance
    return handler


router = APIRouter(tags=["safety"])


@router.post(
    "/clearances/{clearance_id}/submit",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No clearance exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Clearance is not in Defined status (submit_clearance is "
                "single-source from Defined only)."
            ),
        },
    },
    summary="Submit a Defined clearance for review (Defined -> Submitted)",
)
async def post_clearances_submit(
    clearance_id: Annotated[UUID, Path(description="Target clearance's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        SubmitClearance(clearance_id=clearance_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
