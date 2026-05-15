"""MCP tool for the `begin_review_clearance` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.safety._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
)
from cora.safety.features.begin_review_clearance.command import BeginReviewClearance
from cora.safety.features.begin_review_clearance.handler import Handler


class BeginReviewClearanceOutput(BaseModel):
    """Structured output of the `begin_review_clearance` MCP tool."""

    clearance_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `begin_review_clearance` tool on the given MCP server."""

    @mcp.tool(
        name="begin_review_clearance",
        description=(
            "Begin reviewing a Submitted clearance (Submitted -> UnderReview). "
            "Captures the first reviewer's role for audit clarity. "
            "Single-source: requires 'Submitted' status."
        ),
    )
    async def begin_review_clearance_tool(  # pyright: ignore[reportUnusedFunction]
        clearance_id: Annotated[UUID, Field(description="Target clearance's id.")],
        first_reviewer_role: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
                description=(
                    "Facility-vocabulary label for the first reviewer "
                    "(e.g., 'BeamlineScientist', 'LocalContact', 'ESH')."
                ),
            ),
        ],
    ) -> BeginReviewClearanceOutput:
        handler = get_handler()
        await handler(
            BeginReviewClearance(
                clearance_id=clearance_id,
                first_reviewer_role=first_reviewer_role,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return BeginReviewClearanceOutput(clearance_id=clearance_id)
