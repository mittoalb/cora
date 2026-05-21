"""MCP tool for the `hold_run` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.run.features.hold_run.command import HoldRun
from cora.run.features.hold_run.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `hold_run` tool on the given MCP server."""

    @mcp.tool(
        name="hold_run",
        description=(
            "Pause an actively-running Run (Running → Held). "
            "Hold ⇄ Resume is bidirectional and unlimited-cycle. "
            "Re-holding a `Held` Run raises; holding a terminal Run raises."
        ),
    )
    async def hold_run_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        run_id: Annotated[
            UUID,
            Field(description="Target run's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            HoldRun(run_id=run_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
