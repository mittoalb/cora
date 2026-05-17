"""MCP tool for the `revise_agent_budget` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.agent._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.agent.features.revise_agent_budget.command import ReviseAgentBudget
from cora.agent.features.revise_agent_budget.handler import Handler
from cora.infrastructure.observability import current_correlation_id


class ReviseAgentBudgetOutput(BaseModel):
    """Structured output of the `revise_agent_budget` MCP tool."""

    agent_id: UUID
    monthly_usd_cap: float | None
    daily_token_cap: int | None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `revise_agent_budget` tool on the given MCP server."""

    @mcp.tool(
        name="revise_agent_budget",
        description=(
            "Revise an Agent's declarative budget caps. PUT-semantics: the "
            "supplied caps ARE the post-revision budget. Setting both caps to "
            "null clears the budget entirely. Allowed in Defined / Versioned / "
            "Suspended (only Deprecated blocks). Declaration-only at this "
            "iter; enforcement deferred to Budget BC."
        ),
    )
    async def revise_agent_budget_tool(  # pyright: ignore[reportUnusedFunction]
        agent_id: Annotated[UUID, Field(description="Target agent's id.")],
        monthly_usd_cap: Annotated[
            float | None,
            Field(
                default=None,
                ge=0.0,
                description="Monthly USD cap (null to clear this field).",
            ),
        ] = None,
        daily_token_cap: Annotated[
            int | None,
            Field(
                default=None,
                ge=0,
                description="Daily token cap (null to clear this field).",
            ),
        ] = None,
    ) -> ReviseAgentBudgetOutput:
        handler = get_handler()
        await handler(
            ReviseAgentBudget(
                agent_id=agent_id,
                monthly_usd_cap=monthly_usd_cap,
                daily_token_cap=daily_token_cap,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return ReviseAgentBudgetOutput(
            agent_id=agent_id,
            monthly_usd_cap=monthly_usd_cap,
            daily_token_cap=daily_token_cap,
        )
