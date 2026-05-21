"""MCP tool for the `get_decision` query slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.decision.aggregates.decision import (
    DECISION_CHOICE_MAX_LENGTH,
    DECISION_CONTEXT_MAX_LENGTH,
    DecisionNotFoundError,
    confidence_band,
)
from cora.decision.features.get_decision.handler import Handler
from cora.decision.features.get_decision.query import GetDecision
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class DecisionOutput(BaseModel):
    """Structured output of the `get_decision` MCP tool.

    `confidence_band` is a derived field (Low / Medium / High /
    Certain) computed at read time from the stored `confidence`.
    """

    id: UUID
    actor_id: UUID
    context: str = Field(..., max_length=DECISION_CONTEXT_MAX_LENGTH)
    choice: str = Field(..., max_length=DECISION_CHOICE_MAX_LENGTH)
    parent_id: UUID | None
    override_kind: str | None
    decision_rule: str | None
    reasoning: str | None
    confidence: float | None
    confidence_source: str | None
    confidence_band: str | None
    alternatives: list[str]
    decision_inputs: dict[str, Any] | None
    reasoning_signature: str | None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_decision` tool on the given MCP server."""

    @mcp.tool(
        name="get_decision",
        description=(
            "Read the current state of an existing Decision by id. Returns "
            "the full structured-audit metadata including actor, context, "
            "choice, optional parent / override_kind / decision_rule / "
            "decision_inputs / reasoning / confidence / alternatives / "
            "reasoning_signature."
        ),
    )
    async def get_decision_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        decision_id: Annotated[UUID, Field(description="Target decision's id.")],
    ) -> DecisionOutput:
        handler = get_handler()
        decision = await handler(
            GetDecision(decision_id=decision_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if decision is None:
            raise DecisionNotFoundError(decision_id)
        band = confidence_band(decision.confidence)
        return DecisionOutput(
            id=decision.id,
            actor_id=decision.actor_id,
            context=decision.context.value,
            choice=decision.choice.value,
            parent_id=decision.parent_id,
            override_kind=decision.override_kind,
            decision_rule=(
                decision.decision_rule.value if decision.decision_rule is not None else None
            ),
            reasoning=decision.reasoning,
            confidence=decision.confidence,
            confidence_source=(
                decision.confidence_source.value if decision.confidence_source is not None else None
            ),
            confidence_band=band.value if band is not None else None,
            alternatives=list(decision.alternatives),
            decision_inputs=decision.decision_inputs,
            reasoning_signature=decision.reasoning_signature,
        )
