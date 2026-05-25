"""MCP tool for the `start_clearance_review` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
)
from cora.safety.features.start_clearance_review.command import StartClearanceReview
from cora.safety.features.start_clearance_review.handler import Handler


class StartClearanceReviewOutput(BaseModel):
    """Structured output of the `start_clearance_review` MCP tool."""

    clearance_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `start_clearance_review` tool on the given MCP server."""

    @mcp.tool(
        name="start_clearance_review",
        description=(
            "Begin reviewing a Submitted clearance (Submitted -> UnderReview). "
            "Captures the first reviewer's role for audit clarity. "
            "Single-source: requires 'Submitted' status."
        ),
    )
    async def start_clearance_review_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        clearance_id: Annotated[UUID, Field(description="Target clearance's id.")],
        first_reviewer_role: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
                description=(
                    "Facility-vocabulary label for the first reviewer "
                    "(for example, 'BeamlineScientist', 'LocalContact', 'ESH')."
                ),
            ),
        ],
    ) -> StartClearanceReviewOutput:
        handler = get_handler()
        await handler(
            StartClearanceReview(
                clearance_id=clearance_id,
                first_reviewer_role=first_reviewer_role,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return StartClearanceReviewOutput(clearance_id=clearance_id)
