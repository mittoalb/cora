"""MCP tool for the `get_surface` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.trust._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.trust.aggregates.surface import SURFACE_NAME_MAX_LENGTH, SurfaceKind, SurfaceStatus
from cora.trust.features.get_surface.handler import Handler
from cora.trust.features.get_surface.query import GetSurface


class SurfaceOutput(BaseModel):
    """Structured output of the `get_surface` MCP tool."""

    id: UUID
    name: str = Field(..., max_length=SURFACE_NAME_MAX_LENGTH)
    kind: SurfaceKind
    status: SurfaceStatus
    defined_at: datetime
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_surface` tool on the given MCP server."""

    @mcp.tool(
        name="get_surface",
        description="Read the current state of an existing surface by id.",
    )
    async def get_surface_tool(  # pyright: ignore[reportUnusedFunction]
        surface_id: Annotated[UUID, Field(description="Target surface's id.")],
    ) -> SurfaceOutput:
        handler = get_handler()
        surface = await handler(
            GetSurface(surface_id=surface_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        if surface is None:
            msg = f"Surface {surface_id} not found"
            raise ValueError(msg)
        return SurfaceOutput(
            id=surface.id,
            name=surface.name.value,
            kind=surface.kind,
            status=surface.status,
            defined_at=surface.defined_at,
            versioned_at=surface.versioned_at,
            deprecated_at=surface.deprecated_at,
        )
