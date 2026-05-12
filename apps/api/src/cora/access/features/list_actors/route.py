"""HTTP route for the `list_actors` query slice.

`GET /actors?cursor=...&limit=50&status=active` returns
`{"items": [...], "next_cursor": "..." | null}`.

Status filter is `Literal["active", "deactivated"] | None`; omitting
the param returns all statuses (no magic 'all' value — implicit-omit
matches modern REST convention).

Limit defaults to 50, capped at 100. Invalid cursor (corrupt base64,
malformed timestamp/UUID) maps to 422 via the BC's exception handler.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from cora.access.aggregates.actor import ACTOR_NAME_MAX_LENGTH
from cora.access.features.list_actors.handler import Handler
from cora.access.features.list_actors.query import ListActors
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


class ActorSummaryDTO(BaseModel):
    """One actor in a paginated list."""

    actor_id: UUID
    name: str = Field(..., max_length=ACTOR_NAME_MAX_LENGTH)
    status: Literal["active", "deactivated"]
    created_at: datetime


class ActorListResponse(BaseModel):
    """Page of actors plus opaque next-page cursor.

    `next_cursor` is None when no more pages. Pass it back as
    `?cursor=...` to fetch the next page.
    """

    items: list[ActorSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.access.list_actors
    return handler


router = APIRouter(tags=["access"])


@router.get(
    "/actors",
    status_code=status.HTTP_200_OK,
    response_model=ActorListResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Query parameters failed validation OR `cursor` was "
                "malformed (corrupt base64, missing separator, bad "
                "timestamp / UUID)."
            ),
        },
    },
    summary="List actors with cursor pagination",
)
async def list_actors(
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    cursor: Annotated[
        str | None,
        Query(description="Opaque cursor from a previous page's `next_cursor`."),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Page size; capped at 100."),
    ] = 50,
    status_filter: Annotated[
        Literal["active", "deactivated"] | None,
        Query(
            alias="status",
            description=(
                "Optional status filter. Omit to return all statuses; "
                "no 'all' magic value is accepted."
            ),
        ),
    ] = None,
) -> ActorListResponse:
    page = await handler(
        ListActors(cursor=cursor, limit=limit, status=status_filter),
        principal_id=principal_id,
        correlation_id=cid,
    )
    return ActorListResponse(
        items=[
            ActorSummaryDTO(
                actor_id=item.actor_id,
                name=item.name,
                status=item.status,  # type: ignore[arg-type]  # CHECK constraint guarantees it
                created_at=item.created_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
