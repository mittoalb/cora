"""MCP tool for the `submit_clearance` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.safety._bootstrap import SYSTEM_PRINCIPAL_ID
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
        clearance_id: Annotated[UUID, Field(description="Target clearance's id.")],
    ) -> SubmitClearanceOutput:
        handler = get_handler()
        await handler(
            SubmitClearance(clearance_id=clearance_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return SubmitClearanceOutput(clearance_id=clearance_id)
