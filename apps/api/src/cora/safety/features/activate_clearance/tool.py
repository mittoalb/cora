"""MCP tool for the `activate_clearance` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.safety._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.safety.features.activate_clearance.command import ActivateClearance
from cora.safety.features.activate_clearance.handler import Handler


class ActivateClearanceOutput(BaseModel):
    """Structured output of the `activate_clearance` MCP tool."""

    clearance_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `activate_clearance` tool on the given MCP server."""

    @mcp.tool(
        name="activate_clearance",
        description=(
            "Activate an Approved clearance (Approved -> Active). The "
            "clearance becomes effective for Run.start gating. Single-source: "
            "requires clearance to be in 'Approved' status."
        ),
    )
    async def activate_clearance_tool(  # pyright: ignore[reportUnusedFunction]
        clearance_id: Annotated[UUID, Field(description="Target clearance's id.")],
    ) -> ActivateClearanceOutput:
        handler = get_handler()
        await handler(
            ActivateClearance(clearance_id=clearance_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ActivateClearanceOutput(clearance_id=clearance_id)
