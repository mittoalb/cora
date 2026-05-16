"""MCP tool for the `reject_clearance` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.safety._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_REJECT_REASON_MAX_LENGTH,
)
from cora.safety.features.reject_clearance.command import RejectClearance
from cora.safety.features.reject_clearance.handler import Handler


class RejectClearanceOutput(BaseModel):
    """Structured output of the `reject_clearance` MCP tool."""

    clearance_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `reject_clearance` tool on the given MCP server."""

    @mcp.tool(
        name="reject_clearance",
        description=(
            "Reject an UnderReview clearance (UnderReview -> Rejected). "
            "Terminal-bad: rejected clearances cannot be revived; a new "
            "clearance must be registered if the operator wants to retry. "
            "Single-source: requires 'UnderReview' status."
        ),
    )
    async def reject_clearance_tool(  # pyright: ignore[reportUnusedFunction]
        clearance_id: Annotated[UUID, Field(description="Target clearance's id.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CLEARANCE_REJECT_REASON_MAX_LENGTH,
                description="Free-form reason for the rejection (audit breadcrumb).",
            ),
        ],
    ) -> RejectClearanceOutput:
        handler = get_handler()
        # TODO(MCP-auth): when MCP principal extraction lands (SEP-986),
        # swap SYSTEM_PRINCIPAL_ID for the real authenticated principal.
        # Until then, MCP-issued rejections record SYSTEM as the rejecting
        # actor in the event envelope (StoredEvent.principal_id), which is
        # correct for unattended automation flows but wrong for human-
        # mediated MCP calls.
        await handler(
            RejectClearance(
                clearance_id=clearance_id,
                reason=reason,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return RejectClearanceOutput(clearance_id=clearance_id)
