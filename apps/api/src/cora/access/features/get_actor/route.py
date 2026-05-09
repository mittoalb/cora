"""HTTP route for the `get_actor` query slice.

`GET /actors/{actor_id}` returns 200 + ActorResponse on hit, 404 on
miss. The handler returns `Actor | None`; the route maps None to 404
via HTTPException (idiomatic in routes; the BC's exception-handler
infrastructure stays focused on domain/application errors raised
deeper in the stack).
"""

from typing import Annotated
from uuid import UUID

from asgi_correlation_id import correlation_id
from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.access._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.access.aggregates.actor import ACTOR_NAME_MAX_LENGTH
from cora.access.features.get_actor.handler import Handler
from cora.access.features.get_actor.query import GetActor


class ActorResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. Decouples the wire format from
    the domain model so the two can evolve independently (e.g. an
    ActorName invariant change doesn't break older clients).
    """

    id: UUID
    name: str = Field(..., max_length=ACTOR_NAME_MAX_LENGTH)
    is_active: bool


class ErrorResponse(BaseModel):
    """Shared error body for OpenAPI documentation."""

    detail: str


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.access.get_actor
    return handler


def _get_correlation_id() -> UUID:
    raw = correlation_id.get()
    assert raw is not None, "CorrelationIdMiddleware did not set correlation_id"
    return UUID(raw)


def _get_principal_id() -> UUID:
    return SYSTEM_PRINCIPAL_ID


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
    cid: Annotated[UUID, Depends(_get_correlation_id)],
    principal_id: Annotated[UUID, Depends(_get_principal_id)],
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
        is_active=actor.is_active,
    )
