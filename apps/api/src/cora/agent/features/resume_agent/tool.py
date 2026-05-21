"""MCP tool for the `resume_agent` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.agent.features.resume_agent.command import ResumeAgent
from cora.agent.features.resume_agent.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


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
        ctx: Context[Any, Any, Any],
        agent_id: Annotated[UUID, Field(description="Target agent's id.")],
    ) -> ResumeAgentOutput:
        handler = get_handler()
        await handler(
            ResumeAgent(agent_id=agent_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ResumeAgentOutput(agent_id=agent_id)
