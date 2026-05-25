"""HTTP route for the `define_zone` slice.

Pydantic request/response schemas + APIRouter for `POST /zones`. The
slice's BC-level wiring (`cora.trust.routes.register_trust_routes`)
includes this router on the FastAPI app.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.trust.aggregates.zone import ZONE_NAME_MAX_LENGTH
from cora.trust.features.define_zone.command import DefineZone
from cora.trust.features.define_zone.handler import IdempotentHandler


class DefineZoneRequest(BaseModel):
    """Body for `POST /zones`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=ZONE_NAME_MAX_LENGTH,
        description="Display name for the new zone.",
    )


class DefineZoneResponse(BaseModel):
    """Response body for `POST /zones`."""

    zone_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.trust.define_zone
    return handler


router = APIRouter(tags=["trust"])


@router.post(
    "/zones",
    status_code=status.HTTP_201_CREATED,
    response_model=DefineZoneResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (for example whitespace-only name).",
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
    summary="Define a new Trust zone",
)
async def post_zones(
    body: DefineZoneRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied unique key per logical request. "
                "Retries with the same key + same body return the cached "
                "response instead of re-creating the zone. Reusing a key "
                "with a different body returns 422."
            ),
        ),
    ] = None,
) -> DefineZoneResponse:
    zone_id = await handler(
        DefineZone(name=body.name),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return DefineZoneResponse(zone_id=zone_id)
