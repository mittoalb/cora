"""MCP tool for the `get_surface` query slice.

Lifecycle timestamps dropped per Path C — Surface is a
singleton-ish aggregate with no observable read value for those
fields. See route.py docstring for the carve-out reasoning.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.aggregates.surface import SURFACE_NAME_MAX_LENGTH, SurfaceKind, SurfaceStatus
from cora.trust.features.get_surface.handler import Handler
from cora.trust.features.get_surface.query import GetSurface


class SurfaceOutput(BaseModel):
    """Structured output of the `get_surface` MCP tool."""

    id: UUID
    name: str = Field(..., max_length=SURFACE_NAME_MAX_LENGTH)
    kind: SurfaceKind
    status: SurfaceStatus


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_surface` tool on the given MCP server."""

    @mcp.tool(
        name="get_surface",
        description="Read the current state of an existing surface by id.",
    )
    async def get_surface_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        surface_id: Annotated[UUID, Field(description="Target surface's id.")],
    ) -> SurfaceOutput:
        handler = get_handler()
        surface = await handler(
            GetSurface(surface_id=surface_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if surface is None:
            msg = f"Surface {surface_id} not found"
            raise ValueError(msg)
        return SurfaceOutput(
            id=surface.id,
            name=surface.name.value,
            kind=surface.kind,
            status=surface.status,
        )
