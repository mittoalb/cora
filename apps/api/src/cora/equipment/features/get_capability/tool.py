"""MCP tool for the `get_capability` query slice.

Surfaces the same handler the REST route uses. Returns a structured
CapabilityOutput on hit. On miss raises an exception that FastMCP
wraps as `isError: true` with a text diagnostic — matches the REST
404 behaviour in MCP's error idiom (LLM consumers get a clear
"capability not found" message rather than null structuredContent
they have to interpret).
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.aggregates.capability import CAPABILITY_NAME_MAX_LENGTH
from cora.equipment.features.get_capability.handler import Handler
from cora.equipment.features.get_capability.query import GetCapability
from cora.infrastructure.observability import current_correlation_id


class CapabilityOutput(BaseModel):
    """Structured output of the `get_capability` MCP tool."""

    id: UUID
    name: str = Field(..., max_length=CAPABILITY_NAME_MAX_LENGTH)
    status: str


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_capability` tool on the given MCP server."""

    @mcp.tool(
        name="get_capability",
        description="Read the current state of an existing capability by id.",
    )
    async def get_capability_tool(  # pyright: ignore[reportUnusedFunction]
        capability_id: Annotated[
            UUID,
            Field(description="Target capability's id."),
        ],
    ) -> CapabilityOutput:
        handler = get_handler()
        capability = await handler(
            GetCapability(capability_id=capability_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        if capability is None:
            msg = f"Capability {capability_id} not found"
            raise ValueError(msg)
        return CapabilityOutput(
            id=capability.id,
            name=capability.name.value,
            status=capability.status.value,
        )
