"""HTTP route for the `get_actor` query slice.

`GET /actors/{actor_id}` returns 200 + ActorResponse on hit, 404 on
miss. The handler returns `Actor | None`; the route maps None to 404
via HTTPException (idiomatic in routes; the BC's exception-handler
infrastructure stays focused on domain/application errors raised
deeper in the stack).
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.access.aggregates.actor import ACTOR_NAME_MAX_LENGTH
from cora.access.features.get_actor.handler import Handler
from cora.access.features.get_actor.query import GetActor
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


class ActorResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. Decouples the wire format from
    the domain model so the two can evolve independently (for example
    an ActorName invariant change doesn't break older clients).

    `kind` (Phase 8f-a) distinguishes human-registered Actors from
    agent-co-registered Actors (via the Agent BC `define_agent`
    cross-BC atomic write). Existing consumers that don't read `kind`
    are unaffected; consumers that need the distinction (Decision
    projections, audit-policy filters) gain it without polymorphism.
    """

    id: UUID
    name: str = Field(..., max_length=ACTOR_NAME_MAX_LENGTH)
    kind: Literal["human", "agent"]
    is_active: bool


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.access.get_actor
    return handler


router = APIRouter(tags=["access"])


@router.get(
    "/actors/{actor_id}",
    status_code=status.HTTP_200_OK,
    response_model=ActorResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No actor exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get an actor by id",
)
async def get_actors(
    actor_id: Annotated[UUID, Path(description="Target actor's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> ActorResponse:
    actor = await handler(
        GetActor(actor_id=actor_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
    if actor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Actor {actor_id} not found",
        )
    return ActorResponse(
        id=actor.id,
        name=actor.name.value,
        kind=actor.kind.value,  # type: ignore[arg-type]  # ActorKind StrEnum guarantees literal
        is_active=actor.is_active,
    )
