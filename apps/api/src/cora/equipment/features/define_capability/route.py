"""HTTP route for the `define_capability` slice.

Pydantic request/response schemas + APIRouter for `POST /capabilities`.
The slice's BC-level wiring (`cora.equipment.routes.register_equipment_routes`)
includes this router on the FastAPI app.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.capability import CAPABILITY_NAME_MAX_LENGTH
from cora.equipment.features.define_capability.command import DefineCapability
from cora.equipment.features.define_capability.handler import IdempotentHandler
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


class DefineCapabilityRequest(BaseModel):
    """Body for `POST /capabilities`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=CAPABILITY_NAME_MAX_LENGTH,
        description="Display name for the new capability.",
    )


class DefineCapabilityResponse(BaseModel):
    """Response body for `POST /capabilities`."""

    capability_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.equipment.define_capability
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/capabilities",
    status_code=status.HTTP_201_CREATED,
    response_model=DefineCapabilityResponse,
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
    summary="Define a new technique-class capability",
)
async def post_capabilities(
    body: DefineCapabilityRequest,
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
                "response instead of re-creating the capability."
            ),
        ),
    ] = None,
) -> DefineCapabilityResponse:
    capability_id = await handler(
        DefineCapability(name=body.name),
        principal_id=principal_id,
        correlation_id=cid,
        idempotency_key=idempotency_key,
    )
    return DefineCapabilityResponse(capability_id=capability_id)
