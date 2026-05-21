"""MCP tool for the `start_procedure` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation.features.start_procedure.command import StartProcedure
from cora.operation.features.start_procedure.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `start_procedure` tool on the given MCP server."""

    @mcp.tool(
        name="start_procedure",
        description=(
            "Transition an existing Procedure from Defined to Running. "
            "Requires the Procedure to currently be in `Defined`. "
            "Re-starting a `Running` Procedure raises; starting any "
            "terminal raises. Each target Asset is loaded and rejected "
            "if Decommissioned."
        ),
    )
    async def start_procedure_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            StartProcedure(procedure_id=procedure_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
