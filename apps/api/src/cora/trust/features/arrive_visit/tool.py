"""MCP tool for the `arrive_visit` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.features.arrive_visit.command import ArriveVisit
from cora.trust.features.arrive_visit.handler import Handler


class ArriveVisitOutput(BaseModel):
    """Structured output of the `arrive_visit` MCP tool."""

    visit_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `arrive_visit` tool on the given MCP server."""

    @mcp.tool(
        name="arrive_visit",
        description=(
            "Arrive at a Planned Visit (Planned -> Arrived). Explicit "
            "operator gesture; distinct from check_in (Phase gamma)."
        ),
    )
    async def arrive_visit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        visit_id: Annotated[UUID, Field(description="Target Visit's id.")],
    ) -> ArriveVisitOutput:
        handler = get_handler()
        await handler(
            ArriveVisit(visit_id=visit_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ArriveVisitOutput(visit_id=visit_id)
