"""MCP tool for the `start_visit` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.features.start_visit.command import StartVisit
from cora.trust.features.start_visit.handler import Handler


class StartVisitOutput(BaseModel):
    """Structured output of the `start_visit` MCP tool."""

    visit_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `start_visit` tool on the given MCP server."""

    @mcp.tool(
        name="start_visit",
        description=(
            "Start an Arrived Visit (Arrived -> InProgress). Explicit "
            "operator gesture; distinct from take_control_of_surface."
        ),
    )
    async def start_visit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        visit_id: Annotated[UUID, Field(description="Target Visit's id.")],
    ) -> StartVisitOutput:
        handler = get_handler()
        await handler(
            StartVisit(visit_id=visit_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return StartVisitOutput(visit_id=visit_id)
