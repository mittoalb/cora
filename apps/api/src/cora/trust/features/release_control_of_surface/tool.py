"""MCP tool for the `release_control_of_surface` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.features.release_control_of_surface.command import ReleaseControlOfSurface
from cora.trust.features.release_control_of_surface.handler import Handler


class ReleaseControlOfSurfaceOutput(BaseModel):
    """Structured output of the `release_control_of_surface` MCP tool."""

    visit_id: UUID
    surface_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `release_control_of_surface` tool on the given MCP server."""

    @mcp.tool(
        name="release_control_of_surface",
        description=(
            "Requesting Visit releases operational control of the named "
            "Surface. Fails if the requesting Visit is not the current "
            "Surface holder."
        ),
    )
    async def release_control_of_surface_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        visit_id: Annotated[UUID, Field(description="Requesting Visit's id.")],
        surface_id: Annotated[
            UUID,
            Field(
                description=(
                    "Surface the Visit relinquishes control of. Must match the Visit's surface_id."
                )
            ),
        ],
    ) -> ReleaseControlOfSurfaceOutput:
        handler = get_handler()
        await handler(
            ReleaseControlOfSurface(visit_id=visit_id, surface_id=surface_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ReleaseControlOfSurfaceOutput(visit_id=visit_id, surface_id=surface_id)
