"""MCP tool for the `define_conduit` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.aggregates.conduit import CONDUIT_NAME_MAX_LENGTH
from cora.trust.features.define_conduit.command import DefineConduit
from cora.trust.features.define_conduit.handler import IdempotentHandler


class DefineConduitOutput(BaseModel):
    """Structured output of the `define_conduit` MCP tool."""

    conduit_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_conduit` tool on the given MCP server."""

    @mcp.tool(
        name="define_conduit",
        description="Define a new Trust conduit between two zones.",
    )
    async def define_conduit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CONDUIT_NAME_MAX_LENGTH,
                description="Display name for the new conduit.",
            ),
        ],
        source_zone_id: Annotated[
            UUID,
            Field(
                description="UUID of the source endpoint Zone (not validated for existence).",
            ),
        ],
        target_zone_id: Annotated[
            UUID,
            Field(
                description="UUID of the target endpoint Zone (not validated for existence).",
            ),
        ],
    ) -> DefineConduitOutput:
        handler = get_handler()
        conduit_id = await handler(
            DefineConduit(
                name=name,
                source_zone_id=source_zone_id,
                target_zone_id=target_zone_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefineConduitOutput(conduit_id=conduit_id)
