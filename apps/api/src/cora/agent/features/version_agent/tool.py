"""MCP tool for the `version_agent` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.agent._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.agent.features.version_agent.command import VersionAgent
from cora.agent.features.version_agent.handler import Handler
from cora.infrastructure.observability import current_correlation_id


class VersionAgentOutput(BaseModel):
    """Structured output of the `version_agent` MCP tool."""

    agent_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `version_agent` tool on the given MCP server."""

    @mcp.tool(
        name="version_agent",
        description=(
            "Version a Defined Agent (Defined -> Versioned). Promotes the "
            "Agent to ready-for-invocation (Anthropic-Skills-style rainbow-"
            "deploy signal). Source set is {Defined} only; re-versioning a "
            "Versioned Agent OR versioning a Deprecated Agent raises an "
            "error. Multi-version-per-kind is achieved by defining a new "
            "Agent with the same `kind` and a different `id`, not by "
            "re-versioning the same `id`."
        ),
    )
    async def version_agent_tool(  # pyright: ignore[reportUnusedFunction]
        agent_id: Annotated[UUID, Field(description="Target agent's id.")],
    ) -> VersionAgentOutput:
        handler = get_handler()
        await handler(
            VersionAgent(agent_id=agent_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return VersionAgentOutput(agent_id=agent_id)
