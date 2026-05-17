"""MCP tool for the `grant_tool_to_agent` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.agent._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.agent.aggregates.agent import AGENT_TOOL_NAME_MAX_LENGTH
from cora.agent.features.grant_tool_to_agent.command import GrantToolToAgent
from cora.agent.features.grant_tool_to_agent.handler import Handler
from cora.infrastructure.observability import current_correlation_id


class GrantToolToAgentOutput(BaseModel):
    """Structured output of the `grant_tool_to_agent` MCP tool."""

    agent_id: UUID
    tool_name: str


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `grant_tool_to_agent` tool on the given MCP server."""

    @mcp.tool(
        name="grant_tool_to_agent",
        description=(
            "Add one MCP tool to an Agent's per-agent allowlist. Allowed in "
            "Defined / Versioned / Suspended (only Deprecated blocks). "
            "Idempotent: re-granting an existing tool emits no event. Cap is "
            "32 entries per Agent."
        ),
    )
    async def grant_tool_to_agent_tool(  # pyright: ignore[reportUnusedFunction]
        agent_id: Annotated[UUID, Field(description="Target agent's id.")],
        tool_name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=AGENT_TOOL_NAME_MAX_LENGTH,
                description="MCP tool name to add (1-100 chars).",
            ),
        ],
    ) -> GrantToolToAgentOutput:
        handler = get_handler()
        await handler(
            GrantToolToAgent(agent_id=agent_id, tool_name=tool_name),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return GrantToolToAgentOutput(agent_id=agent_id, tool_name=tool_name)
