"""MCP tool for the `suspend_agent` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.agent._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.agent.aggregates.agent import AGENT_SUSPENSION_REASON_MAX_LENGTH
from cora.agent.features.suspend_agent.command import SuspendAgent
from cora.agent.features.suspend_agent.handler import Handler
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class SuspendAgentOutput(BaseModel):
    """Structured output of the `suspend_agent` MCP tool."""

    agent_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `suspend_agent` tool on the given MCP server."""

    @mcp.tool(
        name="suspend_agent",
        description=(
            "Pause a Versioned Agent (Versioned -> Suspended). Non-terminal: "
            "returns to Versioned via `resume_agent`. REQUIRED `reason` (1-500 "
            "chars) carries operator context (cost-overrun, output-spike, "
            "model-regression) for the audit log."
        ),
    )
    async def suspend_agent_tool(  # pyright: ignore[reportUnusedFunction]
        agent_id: Annotated[UUID, Field(description="Target agent's id.")],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=AGENT_SUSPENSION_REASON_MAX_LENGTH,
                description="Operator-supplied suspension reason.",
            ),
        ],
    ) -> SuspendAgentOutput:
        handler = get_handler()
        await handler(
            SuspendAgent(agent_id=agent_id, reason=reason),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return SuspendAgentOutput(agent_id=agent_id)
