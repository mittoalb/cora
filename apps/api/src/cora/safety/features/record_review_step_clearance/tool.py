"""MCP tool for the `record_review_step_clearance` slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.safety._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_REVIEWER_NOTES_MAX_LENGTH,
    CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
)
from cora.safety.features.record_review_step_clearance.command import (
    RecordReviewStepClearance,
)
from cora.safety.features.record_review_step_clearance.handler import Handler


class RecordReviewStepClearanceOutput(BaseModel):
    """Structured output of the `record_review_step_clearance` MCP tool."""

    clearance_id: UUID
    step_index: int


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `record_review_step_clearance` tool on the given MCP server."""

    @mcp.tool(
        name="record_review_step_clearance",
        description=(
            "Append one reviewer step to an UnderReview clearance's chain. "
            "Status stays UnderReview; the chain grows by one. Terminal "
            "Approved/Rejected transitions land via 'approve_clearance' / "
            "'reject_clearance' once the chain is complete. step_index must "
            "equal len(reviewers) at append time (append-only contract)."
        ),
    )
    async def record_review_step_clearance_tool(  # pyright: ignore[reportUnusedFunction]
        clearance_id: Annotated[UUID, Field(description="Target clearance's id.")],
        step_index: Annotated[
            int,
            Field(ge=0, description="0-based step index; must equal len(reviewers)."),
        ],
        role: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
                description="Facility-vocabulary reviewer role.",
            ),
        ],
        decision: Annotated[
            Literal["Approved", "Rejected", "RequestedChanges"],
            Field(description="Reviewer decision for this step."),
        ],
        decided_at: Annotated[
            datetime,
            Field(description="When the reviewer made the decision."),
        ],
        notes: Annotated[
            str | None,
            Field(
                default=None,
                max_length=CLEARANCE_REVIEWER_NOTES_MAX_LENGTH,
                description="Optional reviewer notes.",
            ),
        ] = None,
    ) -> RecordReviewStepClearanceOutput:
        handler = get_handler()
        # TODO(MCP-auth): when MCP principal extraction lands (SEP-986),
        # swap SYSTEM_PRINCIPAL_ID for the real authenticated principal.
        # Until then, MCP-issued review-step appends record SYSTEM as the
        # reviewer's actor_id in the chain entry, which is correct for
        # unattended automation flows but wrong for human-mediated MCP calls.
        await handler(
            RecordReviewStepClearance(
                clearance_id=clearance_id,
                step_index=step_index,
                role=role,
                actor_id=SYSTEM_PRINCIPAL_ID,
                decision=decision,
                decided_at=decided_at,
                notes=notes,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return RecordReviewStepClearanceOutput(clearance_id=clearance_id, step_index=step_index)
