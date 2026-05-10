"""HTTP route for the `define_conduit` slice.

Pydantic request/response schemas + APIRouter for `POST /conduits`.
The slice's BC-level wiring (`cora.trust.routes.register_trust_routes`)
includes this router on the FastAPI app.

Pydantic validates `source_zone_id` / `target_zone_id` as UUIDs
(parsed from JSON strings) but does NOT verify the referenced Zones
exist — that's the eventual-consistency stance documented on the
Conduit aggregate.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.trust.aggregates.conduit import CONDUIT_NAME_MAX_LENGTH
from cora.trust.features.define_conduit.command import DefineConduit
from cora.trust.features.define_conduit.handler import IdempotentHandler


class DefineConduitRequest(BaseModel):
    """Body for `POST /conduits`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=CONDUIT_NAME_MAX_LENGTH,
        description="Display name for the new conduit.",
    )
    source_zone_id: UUID = Field(
        ...,
        description="UUID of the source endpoint Zone (not validated for existence).",
    )
    target_zone_id: UUID = Field(
        ...,
        description="UUID of the target endpoint Zone (not validated for existence).",
    )


class DefineConduitResponse(BaseModel):
    """Response body for `POST /conduits`."""

    conduit_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.trust.define_conduit
    return handler


router = APIRouter(tags=["trust"])


@router.post(
    "/conduits",
    status_code=status.HTTP_201_CREATED,
    response_model=DefineConduitResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (e.g. whitespace-only name).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Define a new Trust conduit between two zones",
)
async def post_conduits(
    body: DefineConduitRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied unique key per logical request. "
                "Retries with the same key + same body return the cached "
                "response instead of re-creating the conduit. Reusing a "
                "key with a different body returns 422."
            ),
        ),
    ] = None,
) -> DefineConduitResponse:
    conduit_id = await handler(
        DefineConduit(
            name=body.name,
            source_zone_id=body.source_zone_id,
            target_zone_id=body.target_zone_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        idempotency_key=idempotency_key,
    )
    return DefineConduitResponse(conduit_id=conduit_id)
