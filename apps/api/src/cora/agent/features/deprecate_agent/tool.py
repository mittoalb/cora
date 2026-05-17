"""MCP tool for the `deprecate_agent` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.agent._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.agent.aggregates.agent import AGENT_DEPRECATION_REASON_MAX_LENGTH
from cora.agent.features.deprecate_agent.command import DeprecateAgent
from cora.agent.features.deprecate_agent.handler import Handler
from cora.infrastructure.observability import current_correlation_id


class DeprecateAgentOutput(BaseModel):
    """Structured output of the `deprecate_agent` MCP tool."""

    agent_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `deprecate_agent` tool on the given MCP server."""

    @mcp.tool(
        name="deprecate_agent",
        description=(
            "Deprecate an Agent (Defined | Versioned -> Deprecated). Terminal: "
            "deprecated Agents cannot be revived. Optional `reason` (1-500 "
            "chars) carries an operator-supplied explanation."
        ),
    )
    async def deprecate_agent_tool(  # pyright: ignore[reportUnusedFunction]
        agent_id: Annotated[UUID, Field(description="Target agent's id.")],
        reason: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=AGENT_DEPRECATION_REASON_MAX_LENGTH,
                description="Optional deprecation reason.",
            ),
        ] = None,
    ) -> DeprecateAgentOutput:
        handler = get_handler()
        await handler(
            DeprecateAgent(agent_id=agent_id, reason=reason),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return DeprecateAgentOutput(agent_id=agent_id)
