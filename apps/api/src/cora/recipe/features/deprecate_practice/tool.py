"""MCP tool for the `deprecate_practice` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.features.deprecate_practice.command import DeprecatePractice
from cora.recipe.features.deprecate_practice.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `deprecate_practice` tool on the given MCP server."""

    @mcp.tool(
        name="deprecate_practice",
        description=(
            "Mark an existing practice as deprecated. Accepts both "
            "Defined and Versioned source states. Re-deprecating an "
            "already-Deprecated practice raises."
        ),
    )
    async def deprecate_practice_tool(  # pyright: ignore[reportUnusedFunction]
        practice_id: Annotated[
            UUID,
            Field(description="Target practice's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DeprecatePractice(practice_id=practice_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
