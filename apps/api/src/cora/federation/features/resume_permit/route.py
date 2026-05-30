"""HTTP route for the `resume_permit` slice.

Action endpoint at `POST /federation/permits/{permit_id}/resume`.
204 No Content on success. No body: resume carries no payload, the
target is identified entirely by the path parameter.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.federation.features.resume_permit.command import ResumePermit
from cora.federation.features.resume_permit.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.resume_permit
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/permits/{permit_id}/resume",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated.",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No permit exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Permit is not in `Suspended` status (resume_permit is single-source "
                "from Suspended; first activation uses activate_permit)."
            ),
        },
    },
    summary="Resume a Suspended Permit back to Active (Suspended -> Active)",
)
async def post_federation_permits_resume(
    permit_id: Annotated[UUID, Path(description="Target permit's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        ResumePermit(permit_id=permit_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
