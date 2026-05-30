"""HTTP route for the `complete_credential_rotation` slice.

Action endpoint at
`POST /federation/credentials/{credential_id}/rotation/complete`. No
body. 204 No Content on success. The `rotation/complete` sub-path
mirrors the supply BC's `POST /supplies/{supply_id}/deregister`
lifecycle-action precedent: rotation phases sit under the resource via
verb so the audit gesture (complete) is distinguishable from a generic
resource update.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.federation.features.complete_credential_rotation.command import (
    CompleteCredentialRotation,
)
from cora.federation.features.complete_credential_rotation.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.complete_credential_rotation
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/credentials/{credential_id}/rotation/complete",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No credential exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Credential is not in `Rotating` status, or pending refs are "
                "absent (complete_credential_rotation is single-source from "
                "Rotating with pending refs populated)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation (not a UUID).",
        },
    },
    summary="Complete an in-flight credential rotation (Rotating -> Active)",
)
async def post_federation_credentials_rotation_complete(
    credential_id: Annotated[UUID, Path(description="Target credential's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        CompleteCredentialRotation(credential_id=credential_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
