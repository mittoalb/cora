"""MCP tool for the `complete_procedure` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.infrastructure.observability import current_correlation_id
from cora.operation._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.operation.features.complete_procedure.command import CompleteProcedure
from cora.operation.features.complete_procedure.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `complete_procedure` tool on the given MCP server."""

    @mcp.tool(
        name="complete_procedure",
        description=(
            "Mark an existing Procedure as completed (happy-path terminal). "
            "Requires the Procedure to currently be in `Running`. "
            "Re-completing an already-`Completed` Procedure raises; "
            "completing an `Aborted` Procedure raises."
        ),
    )
    async def complete_procedure_tool(  # pyright: ignore[reportUnusedFunction]
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            CompleteProcedure(procedure_id=procedure_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
