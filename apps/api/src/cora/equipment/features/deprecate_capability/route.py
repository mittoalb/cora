"""HTTP route for the `deprecate_capability` slice.

Action endpoint at `POST /capabilities/{capability_id}/deprecate`.
No body. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.equipment.features.deprecate_capability.command import DeprecateCapability
from cora.equipment.features.deprecate_capability.handler import Handler
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.deprecate_capability
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/capabilities/{capability_id}/deprecate",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No capability exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Capability is not in `Defined` or `Versioned` status "
                "(deprecate requires one of those — re-deprecating a "
                "Deprecated capability raises), OR a concurrent write "
                "to the same capability stream conflicted (optimistic "
                "concurrency)."
            ),
        },
    },
    summary="Mark an existing capability as deprecated",
)
async def post_capabilities_deprecate(
    capability_id: Annotated[UUID, Path(description="Target capability's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        DeprecateCapability(capability_id=capability_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
