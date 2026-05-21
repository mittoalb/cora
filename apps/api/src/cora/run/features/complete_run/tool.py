"""MCP tool for the `complete_run` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.run.features.complete_run.command import CompleteRun
from cora.run.features.complete_run.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `complete_run` tool on the given MCP server."""

    @mcp.tool(
        name="complete_run",
        description=(
            "Mark an existing Run as completed (happy-path terminal). "
            "Requires the Run to currently be in `Running`. "
            "Re-completing an already-`Completed` Run raises; "
            "completing an `Aborted` Run raises."
        ),
    )
    async def complete_run_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        run_id: Annotated[
            UUID,
            Field(description="Target run's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            CompleteRun(run_id=run_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
