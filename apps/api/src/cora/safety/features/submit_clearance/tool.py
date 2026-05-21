"""MCP tool for the `submit_clearance` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.safety.features.submit_clearance.command import SubmitClearance
from cora.safety.features.submit_clearance.handler import Handler


class SubmitClearanceOutput(BaseModel):
    """Structured output of the `submit_clearance` MCP tool."""

    clearance_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `submit_clearance` tool on the given MCP server."""

    @mcp.tool(
        name="submit_clearance",
        description=(
            "Submit a Defined clearance for review (Defined -> Submitted). "
            "Single-source: requires clearance to be in 'Defined' status."
        ),
    )
    async def submit_clearance_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        clearance_id: Annotated[UUID, Field(description="Target clearance's id.")],
    ) -> SubmitClearanceOutput:
        handler = get_handler()
        await handler(
            SubmitClearance(clearance_id=clearance_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return SubmitClearanceOutput(clearance_id=clearance_id)
