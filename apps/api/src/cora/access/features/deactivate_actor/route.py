"""HTTP route for the `deactivate_actor` slice.

Action endpoint at `POST /actors/{actor_id}/deactivate`. We chose the
action-endpoint pattern over `DELETE /actors/{actor_id}` because:

  - "Deactivate" isn't deletion — the actor stays in the system,
    just with `is_active=False`.
  - A future ReactivateActor would naturally pair as
    `POST /actors/{actor_id}/reactivate`; using DELETE leaves no
    natural counterpart.
  - The verb in the URL matches the command name, keeping intent
    explicit for both human and OpenAPI consumers.

204 No Content on success (action verb, no body to return).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.access._routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.access.features.deactivate_actor.command import DeactivateActor
from cora.access.features.deactivate_actor.handler import Handler


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.access.deactivate_actor
    return handler


router = APIRouter(tags=["access"])


@router.post(
    "/actors/{actor_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No actor exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Actor is already deactivated, OR a concurrent write to the "
                "same actor stream conflicted (optimistic concurrency)."
            ),
        },
    },
    summary="Deactivate an existing actor",
)
async def post_actors_deactivate(
    actor_id: Annotated[UUID, Path(description="Target actor's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        DeactivateActor(actor_id=actor_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
