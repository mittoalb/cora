"""MCP tool for the re_debrief_run slice.

Surfaces the same handler the REST route uses. MCP tools currently
bypass header-based idempotency, so idempotency_key defaults to None
and each MCP invocation is a fresh attempt.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.agent.features.re_debrief_run.command import ReDebriefRun
from cora.agent.features.re_debrief_run.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class ReDebriefRunOutput(BaseModel):
    """Structured output of the `re_debrief_run` MCP tool."""

    decision_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `re_debrief_run` tool on the given MCP server."""

    @mcp.tool(
        name="re_debrief_run",
        description=(
            "Re-invoke the RunDebriefer agent on demand against a specific Run. "
            "Returns the new `decision_id`. Use when an automated Debrief "
            "needs a fresh take (operator rated it `misleading`, the original "
            "landed `DebriefDeferred`, or a new model version landed). "
            "Optional `parent_decision_id` forms a PROV-O wasInformedBy chain "
            "to the prior Decision (must reference the same Run)."
        ),
    )
    async def re_debrief_run_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        run_id: Annotated[
            UUID,
            Field(description="The Run to re-debrief."),
        ],
        parent_decision_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Optional ref to the prior RunDebrief Decision; sets the "
                    "new Decision's `parent_id` to form an audit chain."
                ),
            ),
        ] = None,
    ) -> ReDebriefRunOutput:
        handler = get_handler()
        decision_id = await handler(
            ReDebriefRun(
                run_id=run_id,
                parent_decision_id=parent_decision_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ReDebriefRunOutput(decision_id=decision_id)
