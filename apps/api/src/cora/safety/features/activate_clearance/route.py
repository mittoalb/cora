"""HTTP route for the `activate_clearance` slice.

Action endpoint at `POST /clearances/{clearance_id}/activate`. No body
fields. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.safety.features.activate_clearance.command import ActivateClearance
from cora.safety.features.activate_clearance.handler import Handler


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.safety.activate_clearance
    return handler


router = APIRouter(tags=["safety"])


@router.post(
    "/clearances/{clearance_id}/activate",
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
                "Clearance is not in Approved status (activate_clearance is "
                "single-source from Approved only)."
            ),
        },
    },
    summary="Activate an Approved clearance (Approved -> Active)",
)
async def post_clearances_activate(
    clearance_id: Annotated[UUID, Path(description="Target clearance's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        ActivateClearance(clearance_id=clearance_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
