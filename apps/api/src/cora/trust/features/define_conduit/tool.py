"""MCP tool for the `define_conduit` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust._bootstrap import SYSTEM_PRINCIPAL_ID
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
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefineConduitOutput(conduit_id=conduit_id)
