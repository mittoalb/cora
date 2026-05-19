"""MCP tool for the `deprecate_method` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.features.deprecate_method.command import DeprecateMethod
from cora.recipe.features.deprecate_method.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `deprecate_method` tool on the given MCP server."""

    @mcp.tool(
        name="deprecate_method",
        description=(
            "Mark an existing method as deprecated. Accepts both "
            "Defined and Versioned source states. Re-deprecating an "
            "already-Deprecated method raises."
        ),
    )
    async def deprecate_method_tool(  # pyright: ignore[reportUnusedFunction]
        method_id: Annotated[
            UUID,
            Field(description="Target method's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DeprecateMethod(method_id=method_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
