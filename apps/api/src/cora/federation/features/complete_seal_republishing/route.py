"""HTTP route for the `complete_seal_republishing` slice.

Action endpoint at
`POST /federation/seals/{facility_id}/republishing/complete`. Optional
JSON body carrying the fresh head pointer (`new_head_hash` +
`new_sequence_number`, supplied together or omitted together). 204 No
Content on success. The `republishing/complete` sub-path mirrors the
credential rotation BC's `POST /credentials/{credential_id}/rotation/
complete` lifecycle-action precedent.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.federation.features.complete_seal_republishing.command import (
    CompleteSealRepublishing,
)
from cora.federation.features.complete_seal_republishing.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class CompleteSealRepublishingBody(BaseModel):
    """Optional complete-seal-republishing request body."""

    model_config = {"extra": "forbid"}

    new_head_hash: str | None = Field(
        default=None,
        description=(
            "SHA-256 (lowercase hex) of the fresh head pointer published at "
            "the close of the republish window. Must be supplied together "
            "with new_sequence_number or omitted together (the back-edge "
            "carries both or neither)."
        ),
    )
    new_sequence_number: int | None = Field(
        default=None,
        description=(
            "Monotonic sequence for the fresh head pointer. Strictly greater "
            "than the current sequence number. Must be supplied together "
            "with new_head_hash or omitted together."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.complete_seal_republishing
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/seals/{facility_id}/republishing/complete",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Seal exists for the given facility_id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Seal is not in 'Republishing' status "
                "(complete_seal_republishing is single-source from "
                "Republishing)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": (
                "Body failed schema validation, only one of new_head_hash "
                "and new_sequence_number was supplied, the supplied "
                "new_sequence_number was not strictly greater than the "
                "current value, or both were omitted while the Seal has no "
                "prior head_hash."
            ),
        },
    },
    summary="Complete an in-flight Seal republish (Republishing -> Live)",
)
async def post_federation_seals_republishing_complete(
    facility_id: Annotated[str, Path(description="Target Seal's facility_id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    body: CompleteSealRepublishingBody | None = None,
) -> None:
    await handler(
        CompleteSealRepublishing(
            facility_id=facility_id,
            new_head_hash=body.new_head_hash if body is not None else None,
            new_sequence_number=body.new_sequence_number if body is not None else None,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
