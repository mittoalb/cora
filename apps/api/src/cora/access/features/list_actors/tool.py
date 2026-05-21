"""MCP tool for the `list_actors` query slice.

Surfaces the same handler the REST route uses. Returns a structured
ActorListOutput. Cursor decode failures raise on the handler side and
FastMCP wraps as `isError: true` (matches the REST 422 idiom in MCP
error semantics).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.access.aggregates.actor import ACTOR_NAME_MAX_LENGTH
from cora.access.features.list_actors.handler import Handler
from cora.access.features.list_actors.query import ListActors
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class ActorSummaryRow(BaseModel):
    """One actor in the list output."""

    actor_id: UUID
    name: str = Field(..., max_length=ACTOR_NAME_MAX_LENGTH)
    kind: Literal["human", "agent", "service_account"]
    status: Literal["active", "deactivated"]
    created_at: datetime


class ActorListOutput(BaseModel):
    """Structured output of the `list_actors` MCP tool."""

    items: list[ActorSummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_actors` tool on the given MCP server."""

    @mcp.tool(
        name="list_actors",
        description=(
            "Cursor-paginated list of actors. Pass `cursor` from a "
            "previous page's `next_cursor` to fetch the next page. "
            "Optional `status` filter accepts 'active' or 'deactivated'."
        ),
    )
    async def list_actors_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        status: Annotated[
            Literal["active", "deactivated"] | None,
            Field(description="Optional status filter; omit to list all."),
        ] = None,
    ) -> ActorListOutput:
        handler = get_handler()
        page = await handler(
            ListActors(cursor=cursor, limit=limit, status=status),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ActorListOutput(
            items=[
                ActorSummaryRow(
                    actor_id=item.actor_id,
                    name=item.name,
                    kind=item.kind,
                    status=item.status,
                    created_at=item.created_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
