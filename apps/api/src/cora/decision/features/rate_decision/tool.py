"""MCP tool for the `rate_decision` slice (Phase 8f-b iter 1).

Surfaces the same handler the REST route uses. Returns a structured
ack with the rated decision_id (matches the 204-equivalent shape
convention from Caution `retire_caution` + Agent `version_agent`).
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.decision._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.decision.aggregates.decision import (
    DECISION_RATING_COMMENT_MAX_LENGTH,
    DecisionRating,
)
from cora.decision.features.rate_decision.command import RateDecision
from cora.decision.features.rate_decision.handler import Handler
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RateDecisionOutput(BaseModel):
    """Structured output of the `rate_decision` MCP tool."""

    decision_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `rate_decision` tool on the given MCP server."""

    @mcp.tool(
        name="rate_decision",
        description=(
            "Rate a Decision (operator acceptance-signal capture). "
            "Closed rating: `useful` (decision helped), `misleading` "
            "(decision led astray), or `ignored` (operator saw it but "
            "chose not to act; positive marker distinct from no-rating). "
            "Optional comment (1-2000 chars). Multiple ratings per "
            "(decision, actor) pair are allowed; the projection takes "
            "latest-per-actor wins. NOT idempotency-wrapped."
        ),
    )
    async def rate_decision_tool(  # pyright: ignore[reportUnusedFunction]
        decision_id: Annotated[UUID, Field(description="Target Decision's id.")],
        rating: Annotated[DecisionRating, Field(description="Closed rating value.")],
        comment: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=DECISION_RATING_COMMENT_MAX_LENGTH,
                description="Optional free-form comment.",
            ),
        ] = None,
    ) -> RateDecisionOutput:
        handler = get_handler()
        await handler(
            RateDecision(decision_id=decision_id, rating=rating, comment=comment),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RateDecisionOutput(decision_id=decision_id)
