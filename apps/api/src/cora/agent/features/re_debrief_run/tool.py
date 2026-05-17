"""MCP tool for the `re_debrief_run` slice.

Surfaces the same handler the REST route uses. MCP tools currently
bypass header extraction and use `SYSTEM_PRINCIPAL_ID` until the
MCP auth-flow phase lands; for the same reason, `idempotency_key`
defaults to `None` so each MCP invocation is a fresh attempt.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.agent._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.agent.features.re_debrief_run.command import ReDebriefRun
from cora.agent.features.re_debrief_run.handler import IdempotentHandler
from cora.infrastructure.observability import current_correlation_id


class ReDebriefRunOutput(BaseModel):
    """Structured output of the `re_debrief_run` MCP tool."""

    decision_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `re_debrief_run` tool on the given MCP server."""

    @mcp.tool(
        name="re_debrief_run",
        description=(
            "Re-invoke the RunDebrief agent on demand against a specific Run. "
            "Returns the new `decision_id`. Use when an automated Debrief "
            "needs a fresh take (operator rated it `misleading`, the original "
            "landed `DebriefDeferred`, or a new model version landed). "
            "Optional `parent_decision_id` forms a PROV-O wasInformedBy chain "
            "to the prior Decision (must reference the same Run)."
        ),
    )
    async def re_debrief_run_tool(  # pyright: ignore[reportUnusedFunction]
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
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return ReDebriefRunOutput(decision_id=decision_id)
