"""HTTP route for the `forget_actor` PII-erasure slice.

`DELETE /actors/{actor_id}/profile` returns 204 on success.

Per the design memo lock: DELETE is the right verb for "erase this
resource" (specifically the PII vault row, not the actor itself —
the Actor aggregate stays in the event log as a pseudonymised
reference per EDPB 01/2025 Example 10). Idempotency-Key support is
mandatory: forget is destructive enough that a double-click must
not append two audit events.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Request, status

from cora.access.features.forget_actor.command import ForgetActor
from cora.access.features.forget_actor.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.access.forget_actor
    return handler


router = APIRouter(tags=["access"])


@router.delete(
    "/actors/{actor_id}/profile",
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
                "Concurrent write to the same actor stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Path parameter failed schema validation OR Idempotency-Key "
                "was reused with a different request."
            ),
        },
    },
    summary="Erase an actor's PII vault row (right to be forgotten)",
)
async def delete_actor_profile(
    actor_id: Annotated[UUID, Path(description="Target actor's id.")],
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied unique key per logical erasure "
                "request. Retries with the same key short-circuit so a "
                "double-click does not append two audit events."
            ),
        ),
    ] = None,
) -> None:
    await handler(
        ForgetActor(actor_id=actor_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
