"""MCP tool for the `take_control_of_surface` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.features.take_control_of_surface.command import TakeControlOfSurface
from cora.trust.features.take_control_of_surface.handler import Handler


class TakeControlOfSurfaceOutput(BaseModel):
    """Structured output of the `take_control_of_surface` MCP tool."""

    visit_id: UUID
    surface_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `take_control_of_surface` tool on the given MCP server."""

    @mcp.tool(
        name="take_control_of_surface",
        description=(
            "Requesting Visit takes operational control of the named "
            "Surface. A part_of descendant Visit may take control from "
            "its parent; any other Visit needs the Surface to be free."
        ),
    )
    async def take_control_of_surface_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        visit_id: Annotated[UUID, Field(description="Requesting Visit's id.")],
        surface_id: Annotated[
            UUID,
            Field(
                description=(
                    "Surface the Visit takes control of. Must match the Visit's surface_id."
                )
            ),
        ],
    ) -> TakeControlOfSurfaceOutput:
        handler = get_handler()
        await handler(
            TakeControlOfSurface(visit_id=visit_id, surface_id=surface_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return TakeControlOfSurfaceOutput(visit_id=visit_id, surface_id=surface_id)
