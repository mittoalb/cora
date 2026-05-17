"""MCP tool for the `resume_agent` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.agent._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.agent.features.resume_agent.command import ResumeAgent
from cora.agent.features.resume_agent.handler import Handler
from cora.infrastructure.observability import current_correlation_id


class ResumeAgentOutput(BaseModel):
    """Structured output of the `resume_agent` MCP tool."""

    agent_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `resume_agent` tool on the given MCP server."""

    @mcp.tool(
        name="resume_agent",
        description=(
            "Return a Suspended Agent to Versioned. No `reason` field by "
            "design: the act of resuming is its own signal; if rationale "
            "matters, record a Decision separately."
        ),
    )
    async def resume_agent_tool(  # pyright: ignore[reportUnusedFunction]
        agent_id: Annotated[UUID, Field(description="Target agent's id.")],
    ) -> ResumeAgentOutput:
        handler = get_handler()
        await handler(
            ResumeAgent(agent_id=agent_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return ResumeAgentOutput(agent_id=agent_id)
