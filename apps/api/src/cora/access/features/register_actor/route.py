"""HTTP route for the `register_actor` slice.

Pydantic request/response schemas + APIRouter for `POST /actors`. The
slice's BC-level wiring (`cora.access.routes.register_access_routes`)
includes this router on the FastAPI app.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.access.aggregates.actor import ACTOR_NAME_MAX_LENGTH, ActorKind
from cora.access.features.register_actor.command import RegisterActor
from cora.access.features.register_actor.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class RegisterActorRequest(BaseModel):
    """Body for `POST /actors`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=ACTOR_NAME_MAX_LENGTH,
        description="Display name for the new actor.",
    )
    # `agent` is deliberately NOT in the closed set — agent Actors come
    # from the cross-BC atomic write in /agents (define_agent slice) so
    # the (Agent.id == Actor.id) lock holds. The decider also rejects
    # kind="agent" with 400 as defense-in-depth.
    kind: Literal["human", "service_account"] = Field(
        default="human",
        description=(
            "Closed discriminator. 'human' (default) for operator "
            "registration. 'service_account' for machine callers: "
            "CI bridges, autonomous agent runtime processes, future "
            "TomoScan / EPICS bridges. 'agent'-kind Actors are minted "
            "exclusively via POST /agents (cross-BC atomic write); this "
            "endpoint rejects it with 400."
        ),
    )


class RegisterActorResponse(BaseModel):
    """Response body for `POST /actors`."""

    actor_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.access.register_actor
    return handler


router = APIRouter(tags=["access"])


@router.post(
    "/actors",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterActorResponse,
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
    summary="Register a new actor",
)
async def post_actors(
    body: RegisterActorRequest,
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
                "response instead of re-creating the actor. Reusing a key "
                "with a different body returns 422."
            ),
        ),
    ] = None,
) -> RegisterActorResponse:
    actor_id = await handler(
        RegisterActor(name=body.name, kind=ActorKind(body.kind)),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterActorResponse(actor_id=actor_id)
