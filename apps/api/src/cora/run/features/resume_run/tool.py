"""MCP tool for the `resume_run` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.infrastructure.observability import current_correlation_id
from cora.run._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.run.features.resume_run.command import ResumeRun
from cora.run.features.resume_run.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `resume_run` tool on the given MCP server."""

    @mcp.tool(
        name="resume_run",
        description=(
            "Resume a held Run (Held → Running). The inverse of hold_run. "
            "Resuming a `Running` Run raises; resuming a terminal Run raises."
        ),
    )
    async def resume_run_tool(  # pyright: ignore[reportUnusedFunction]
        run_id: Annotated[
            UUID,
            Field(description="Target run's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            ResumeRun(run_id=run_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
