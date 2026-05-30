"""HTTP route for the `activate_permit` slice.

Action endpoint at `POST /federation/permits/{permit_id}/activate`.
No request body (the path identifies the target and the principal
identifies the actor). 204 No Content on success.

Mirrors the `mark_supply_available` / `activate_clearance` action-
endpoint shape. No Idempotency-Key header because transition
handlers use strict-not-idempotent guards at the decider; HTTP-layer
caching adds no value.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.federation.features.activate_permit.command import ActivatePermit
from cora.federation.features.activate_permit.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.activate_permit
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/permits/{permit_id}/activate",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
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
                "Permit is not in `Defined` status (activate_permit is "
                "single-source from Defined only)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation (not a UUID).",
        },
    },
    summary="Activate a Defined permit (Defined -> Active)",
)
async def post_federation_permits_activate(
    permit_id: Annotated[UUID, Path(description="Target permit's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        ActivatePermit(permit_id=permit_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
