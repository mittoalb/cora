"""HTTP route for the `start_credential_rotation` slice.

Action endpoint at
`POST /federation/credentials/{credential_id}/rotation/start`. The
path identifies the target credential; the body carries the pending
opaque refs the rotation will promote on completion. 204 No Content
on success.

Mirrors the `activate_permit` / `revoke_permit` action-endpoint shape
in placing the verb under the resource segment, but takes a body
because the pending refs are part of the rotation intent. No
Idempotency-Key header because transition handlers use strict-not-
idempotent guards at the decider; HTTP-layer caching adds no value.

Per AH#6 of [[project_federation_port_design]] Memo 1, the body
carries OPAQUE POINTERS only; raw secret bytes must never cross this
boundary and the caller is responsible for provisioning material in
the SecretStore adapter prior to invoking this endpoint.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.federation.features.start_credential_rotation.command import (
    StartCredentialRotation,
)
from cora.federation.features.start_credential_rotation.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class StartCredentialRotationRequest(BaseModel):
    """Body for `POST /federation/credentials/{credential_id}/rotation/start`."""

    new_secret_ref: str = Field(
        ...,
        min_length=1,
        description=(
            "Opaque pointer to the pending secret material. Must differ "
            "from the credential's current secret_ref. The raw secret "
            "bytes never cross this boundary; the caller is responsible "
            "for SecretStore provisioning."
        ),
    )
    new_public_material_ref: str | None = Field(
        None,
        description=(
            "Optional opaque pointer to the pending public counterpart "
            "(verification key, certificate handle). None when the "
            "purpose is symmetric or the public half lives elsewhere."
        ),
    )

    model_config = {"extra": "forbid"}


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.start_credential_rotation
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/credentials/{credential_id}/rotation/start",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": ("Domain invariant violated (whitespace-only new_secret_ref)."),
        },
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
                "Credential is not in `Active` status, or the supplied "
                "new_secret_ref matches the current secret_ref "
                "(start_credential_rotation is single-source from Active "
                "only and strict-not-idempotent)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": ("Path parameter or request body failed schema validation."),
        },
    },
    summary="Start a rotation against an Active credential (Active -> Rotating)",
)
async def post_federation_credentials_rotation_start(
    credential_id: Annotated[UUID, Path(description="Target credential's id.")],
    body: StartCredentialRotationRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        StartCredentialRotation(
            credential_id=credential_id,
            new_secret_ref=body.new_secret_ref,
            new_public_material_ref=body.new_public_material_ref,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
