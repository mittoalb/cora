"""MCP tool for the `define_zone` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool an MCP-aware client (for example Claude) can call.

MCP tool calls don't currently support idempotency keys (no MCP
standard for client-supplied retry tags); the wrapped handler is
invoked with idempotency_key=None.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.aggregates.zone import ZONE_NAME_MAX_LENGTH
from cora.trust.features.define_zone.command import DefineZone
from cora.trust.features.define_zone.handler import IdempotentHandler


class DefineZoneOutput(BaseModel):
    """Structured output of the `define_zone` MCP tool."""

    zone_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_zone` tool on the given MCP server."""

    @mcp.tool(
        name="define_zone",
        description="Define a new Trust zone with the given display name.",
    )
    async def define_zone_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=ZONE_NAME_MAX_LENGTH,
                description="Display name for the new zone.",
            ),
        ],
    ) -> DefineZoneOutput:
        handler = get_handler()
        zone_id = await handler(
            DefineZone(name=name),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefineZoneOutput(zone_id=zone_id)
