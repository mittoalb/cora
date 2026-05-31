"""HTTP route for the `start_seal_republishing` slice.

Action endpoint at
`POST /federation/seals/{facility_id}/republishing/start`. The path
identifies the target Seal singleton by facility; the body carries
the optional operator `reason` note. 204 No Content on success.

Mirrors the action-endpoint shape of
`POST /federation/credentials/{credential_id}/rotation/start`, but
takes `facility_id` (str) as the singleton key rather than a UUID
because the Seal's domain identity is the facility string; the
handler derives the stream UUID via UUID5.

No Idempotency-Key header because transition handlers use strict-
not-idempotent guards at the decider; HTTP-layer caching adds no
value.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.federation.features.start_seal_republishing.command import (
    StartSealRepublishing,
)
from cora.federation.features.start_seal_republishing.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class StartSealRepublishingRequest(BaseModel):
    """Body for `POST /federation/seals/{facility_id}/republishing/start`."""

    reason: str | None = Field(
        None,
        description=(
            "Optional operator note explaining why republishing was "
            "started (key compromise drill, root rotation, tree "
            "rewrite). Flows onto the SealRepublishingStarted event "
            "payload (audit-log breadcrumb)."
        ),
    )

    model_config = {"extra": "forbid"}


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.start_seal_republishing
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/seals/{facility_id}/republishing/start",
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
                "Seal is not in `Live` status (start_seal_republishing "
                "is single-source from Live only and strict-not-"
                "idempotent)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": ("Path parameter or request body failed schema validation."),
        },
    },
    summary="Start a republishing window on the Live Seal (Live -> Republishing)",
)
async def post_federation_seals_republishing_start(
    facility_id: Annotated[str, Path(description="Target Seal's facility id.")],
    body: StartSealRepublishingRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        StartSealRepublishing(
            facility_id=facility_id,
            reason=body.reason,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
