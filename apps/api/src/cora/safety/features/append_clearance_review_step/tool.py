"""MCP tool for the `append_clearance_review_step` slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_REVIEWER_NOTES_MAX_LENGTH,
    CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
)
from cora.safety.features.append_clearance_review_step.command import (
    AppendClearanceReviewStep,
)
from cora.safety.features.append_clearance_review_step.handler import Handler


class AppendClearanceReviewStepOutput(BaseModel):
    """Structured output of the `append_clearance_review_step` MCP tool."""

    clearance_id: UUID
    step_index: int


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `append_clearance_review_step` tool on the given MCP server."""

    @mcp.tool(
        name="append_clearance_review_step",
        description=(
            "Append one reviewer step to an UnderReview clearance's chain. "
            "Status stays UnderReview; the chain grows by one. Terminal "
            "Approved/Rejected transitions land via 'approve_clearance' / "
            "'reject_clearance' once the chain is complete. step_index must "
            "equal len(review_steps) at append time (append-only contract)."
        ),
    )
    async def append_clearance_review_step_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        clearance_id: Annotated[UUID, Field(description="Target clearance's id.")],
        step_index: Annotated[
            int,
            Field(ge=0, description="0-based step index; must equal len(review_steps)."),
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
    ) -> AppendClearanceReviewStepOutput:
        handler = get_handler()
        await handler(
            AppendClearanceReviewStep(
                clearance_id=clearance_id,
                step_index=step_index,
                role=role,
                actor_id=get_mcp_principal_id(ctx),
                decision=decision,
                decided_at=decided_at,
                notes=notes,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return AppendClearanceReviewStepOutput(clearance_id=clearance_id, step_index=step_index)
