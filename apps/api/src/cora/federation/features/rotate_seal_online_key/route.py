"""HTTP route for the `rotate_seal_online_key` slice.

Action endpoint at
`POST /federation/seals/{facility_id}/online-key/rotate`. JSON body
carries the new online key reference; 204 No Content on success.
Mirrors the supply-BC and federation-Permit pattern of lifecycle
transitions under the resource via verb, not as a PATCH or DELETE, so
the audit gesture (rotate) is distinguishable from a partial-update
semantic.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.federation.features.rotate_seal_online_key.command import (
    RotateSealOnlineKey,
)
from cora.federation.features.rotate_seal_online_key.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class RotateSealOnlineKeyBody(BaseModel):
    """Request body for rotate-seal-online-key."""

    model_config = {"extra": "forbid"}

    new_online_key_ref: UUID = Field(
        description=(
            "Credential id of the fresh online (warm) signing key. Must "
            "differ from both the current online_key_ref (no-op rotation "
            "rejected) and the current offline_key_ref (key-separation "
            "invariant)."
        ),
    )
    signed_by_offline_root: bool = Field(
        description=(
            "Operator affirmation that the offline (cold) root "
            "countersigned this rotation. Required for the audit denorm; "
            "the offline-signature verification itself is out of scope "
            "for this slice."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.rotate_seal_online_key
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/seals/{facility_id}/online-key/rotate",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Seal exists for the given facility.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Seal is not Live (rotate requires Live) or the new ref "
                "equals the current online_key_ref (no-op rotation "
                "rejected)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": (
                "The new online ref equals the current offline_key_ref (key-separation invariant)."
            ),
        },
    },
    summary="Rotate the Seal singleton's online (warm) signing key",
)
async def post_federation_seals_rotate_online_key(
    facility_id: Annotated[str, Path(description="Target Seal's facility id.")],
    body: RotateSealOnlineKeyBody,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RotateSealOnlineKey(
            facility_id=facility_id,
            new_online_key_ref=body.new_online_key_ref,
            signed_by_offline_root=body.signed_by_offline_root,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
