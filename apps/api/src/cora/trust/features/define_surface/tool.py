"""MCP tool for the `define_surface` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust._bootstrap import SYSTEM_PRINCIPAL_ID
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
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefineSurfaceOutput(surface_id=surface_id)
