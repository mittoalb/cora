"""MCP tool for the `approve_clearance` slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.safety._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.safety.features.approve_clearance.command import ApproveClearance
from cora.safety.features.approve_clearance.handler import Handler


class ApproveClearanceOutput(BaseModel):
    """Structured output of the `approve_clearance` MCP tool."""

    clearance_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `approve_clearance` tool on the given MCP server."""

    @mcp.tool(
        name="approve_clearance",
        description=(
            "Approve an UnderReview clearance (UnderReview -> Approved). "
            "Requires the terminal (last) review step to have "
            "decision='Approved'. Optionally refines the validity window. "
            "Single-source: requires 'UnderReview' status."
        ),
    )
    async def approve_clearance_tool(  # pyright: ignore[reportUnusedFunction]
        clearance_id: Annotated[UUID, Field(description="Target clearance's id.")],
        valid_from: Annotated[
            datetime | None,
            Field(default=None, description="Optional effective-from override."),
        ] = None,
        valid_until: Annotated[
            datetime | None,
            Field(default=None, description="Optional effective-until override."),
        ] = None,
    ) -> ApproveClearanceOutput:
        handler = get_handler()
        # TODO(MCP-auth): when MCP principal extraction lands (SEP-986),
        # swap SYSTEM_PRINCIPAL_ID for the real authenticated principal.
        # Until then, MCP-issued approvals record SYSTEM as the approving
        # actor in the event envelope (StoredEvent.principal_id), which is
        # correct for unattended automation flows but wrong for human-
        # mediated MCP calls.
        await handler(
            ApproveClearance(
                clearance_id=clearance_id,
                valid_from=valid_from,
                valid_until=valid_until,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ApproveClearanceOutput(clearance_id=clearance_id)
