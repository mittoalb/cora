"""MCP tool for the `define_surface` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.aggregates.surface import SURFACE_NAME_MAX_LENGTH, SurfaceKind
from cora.trust.features.define_surface.command import DefineSurface
from cora.trust.features.define_surface.handler import IdempotentHandler


class DefineSurfaceOutput(BaseModel):
    """Structured output of the `define_surface` MCP tool."""

    surface_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_surface` tool on the given MCP server."""

    @mcp.tool(
        name="define_surface",
        description="Define a new arrival Surface (HTTP, MCP stdio, MCP streamable-http).",
    )
    async def define_surface_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=SURFACE_NAME_MAX_LENGTH,
                description="Display name for the new surface.",
            ),
        ],
        kind: Annotated[
            SurfaceKind,
            Field(description="Process-level arrival kind."),
        ],
    ) -> DefineSurfaceOutput:
        handler = get_handler()
        surface_id = await handler(
            DefineSurface(name=name, kind=kind),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefineSurfaceOutput(surface_id=surface_id)
