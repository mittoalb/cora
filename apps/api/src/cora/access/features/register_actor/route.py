"""HTTP route for the `register_actor` slice.

Pydantic request/response schemas + APIRouter for `POST /actors`. The
slice's BC-level wiring (`cora.access.routes.register_access_routes`)
includes this router on the FastAPI app.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from cora.access._routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.access.aggregates.actor import ACTOR_NAME_MAX_LENGTH
from cora.access.features.register_actor.command import RegisterActor
from cora.access.features.register_actor.handler import Handler


class RegisterActorRequest(BaseModel):
    """Body for `POST /actors`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=ACTOR_NAME_MAX_LENGTH,
        description="Display name for the new actor.",
    )


class RegisterActorResponse(BaseModel):
    """Response body for `POST /actors`."""

    actor_id: UUID


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.access.register_actor
    return handler


router = APIRouter(tags=["access"])


@router.post(
    "/actors",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterActorResponse,
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
            "description": "Request body failed schema validation.",
        },
    },
    summary="Register a new actor",
)
async def post_actors(
    body: RegisterActorRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> RegisterActorResponse:
    actor_id = await handler(
        RegisterActor(name=body.name),
        principal_id=principal_id,
        correlation_id=cid,
    )
    return RegisterActorResponse(actor_id=actor_id)
