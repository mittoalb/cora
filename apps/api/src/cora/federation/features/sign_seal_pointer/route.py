"""HTTP route for the `sign_seal_pointer` slice.

Action endpoint at
`POST /federation/seals/{facility_id}/pointer/sign`. The path identifies
the per-facility singleton; the body carries the new head hash and the
monotonic sequence number for the signed pointer. 204 No Content on
success.

Mirrors the sibling `rotate_seal_online_key` shape: a part-of-Seal noun
(`pointer`) followed by the transition verb (`sign`) at the tail. Takes
a body because the signed pointer's hash and sequence number are part
of the signing intent. No Idempotency-Key header because transition
handlers use strict-not-idempotent guards at the decider; HTTP-layer
caching adds no value.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.federation.features.sign_seal_pointer.command import SignSealPointer
from cora.federation.features.sign_seal_pointer.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class SignSealPointerRequest(BaseModel):
    """Body for `POST /federation/seals/{facility_id}/pointer/sign`."""

    new_head_hash: str = Field(
        ...,
        min_length=1,
        description=(
            "SHA-256 lowercase hex of the canonicalized head pointer "
            "body just signed by the online key."
        ),
    )
    new_sequence_number: int = Field(
        ...,
        ge=1,
        description=(
            "Monotonic counter for the signed pointer chain. Must "
            "strictly exceed the Seal's current_sequence_number; the "
            "decider rejects regressions."
        ),
    )

    model_config = {"extra": "forbid"}


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.sign_seal_pointer
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/seals/{facility_id}/pointer/sign",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="sign_seal_pointer",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (whitespace-only new_head_hash).",
        },
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
                "Seal is not in `Live` status, or the supplied "
                "new_sequence_number does not strictly exceed the prior "
                "(sign_seal_pointer is single-source from Live only and "
                "strict-not-idempotent)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Sign a new head pointer on a Live Seal (Live -> Live)",
)
async def post_federation_seals_pointer_sign(
    facility_id: Annotated[str, Path(min_length=1, description="Target facility's id.")],
    body: SignSealPointerRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        SignSealPointer(
            facility_id=facility_id,
            new_head_hash=body.new_head_hash,
            new_sequence_number=body.new_sequence_number,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
