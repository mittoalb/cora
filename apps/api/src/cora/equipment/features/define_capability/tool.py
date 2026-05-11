"""MCP tool for the `define_capability` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. MCP tools currently bypass header extraction
and use `SYSTEM_PRINCIPAL_ID` directly until the MCP auth-flow
phase lands.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.aggregates.capability import CAPABILITY_NAME_MAX_LENGTH
from cora.equipment.features.define_capability.command import DefineCapability
from cora.equipment.features.define_capability.handler import IdempotentHandler
from cora.infrastructure.observability import current_correlation_id


class DefineCapabilityOutput(BaseModel):
    """Structured output of the `define_capability` MCP tool."""

    capability_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_capability` tool on the given MCP server."""

    @mcp.tool(
        name="define_capability",
        description="Define a new technique-class capability with the given display name.",
    )
    async def define_capability_tool(  # pyright: ignore[reportUnusedFunction]
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CAPABILITY_NAME_MAX_LENGTH,
                description="Display name for the new capability.",
            ),
        ],
    ) -> DefineCapabilityOutput:
        handler = get_handler()
        capability_id = await handler(
            DefineCapability(name=name),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return DefineCapabilityOutput(capability_id=capability_id)
