"""HTTP route for the `revoke_credential` slice.

Action endpoint at `POST /federation/credentials/{credential_id}/revoke`.
Optional JSON body with a free-text `reason` field; 204 No Content on
success. Mirrors the supply BC's lifecycle-terminal
`POST /supplies/{supply_id}/deregister` and federation's
`POST /federation/permits/{permit_id}/revoke`: lifecycle-state
transitions sit under the resource via verb, not as a DELETE, so the
audit gesture (revoke) is distinguishable from a resource-delete
semantic.

The `reason` body field is accepted but NOT persisted on the
`CredentialRevoked` event today; it is forward-compatibility for a
future audit-narrative breadcrumb on the Decision-BC audit
emission's `reasoning` field.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.federation.features.revoke_credential.command import RevokeCredential
from cora.federation.features.revoke_credential.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class RevokeCredentialBody(BaseModel):
    """Optional revoke-credential request body."""

    reason: str | None = Field(
        default=None,
        description=(
            "Optional free-text operator intent for the revoke. Accepted at "
            "the schema boundary but not persisted on the CredentialRevoked "
            "event today; reserved for a future audit-narrative wiring."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.revoke_credential
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/credentials/{credential_id}/revoke",
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
                "Credential is already Revoked (revoke_credential is "
                "strict-not-idempotent; Revoked is terminal)."
            ),
        },
    },
    summary="Revoke a Credential (terminal: any non-Revoked -> Revoked)",
)
async def post_federation_credentials_revoke(
    credential_id: Annotated[UUID, Path(description="Target credential's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    body: RevokeCredentialBody | None = None,
) -> None:
    await handler(
        RevokeCredential(
            credential_id=credential_id,
            reason=body.reason if body is not None else None,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
