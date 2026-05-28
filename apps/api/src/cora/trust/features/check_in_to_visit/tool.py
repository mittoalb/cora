"""MCP tool for the `check_in_to_visit` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.aggregates.visit import PresenceMode
from cora.trust.features.check_in_to_visit.command import CheckInToVisit
from cora.trust.features.check_in_to_visit.handler import Handler


class CheckInToVisitOutput(BaseModel):
    """Structured output of the `check_in_to_visit` MCP tool."""

    visit_id: UUID
    actor_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `check_in_to_visit` tool on the given MCP server."""

    @mcp.tool(
        name="check_in_to_visit",
        description=(
            "Check an actor in to a Visit (physical on-site or remote). "
            "Visit must be Arrived / InProgress / OnHold (presence is "
            "orthogonal to lifecycle; operator must arrive_visit first). "
            "Actor cannot have an existing open presence entry."
        ),
    )
    async def check_in_to_visit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        visit_id: Annotated[UUID, Field(description="Target Visit's id.")],
        actor_id: Annotated[UUID, Field(description="Actor checking in.")],
        mode: Annotated[
            PresenceMode,
            Field(description="physical (on-site) or remote (e.g., remote API driver)."),
        ],
    ) -> CheckInToVisitOutput:
        handler = get_handler()
        await handler(
            CheckInToVisit(visit_id=visit_id, actor_id=actor_id, mode=mode),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return CheckInToVisitOutput(visit_id=visit_id, actor_id=actor_id)
