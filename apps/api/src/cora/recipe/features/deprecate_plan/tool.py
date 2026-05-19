"""MCP tool for the `deprecate_plan` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.features.deprecate_plan.command import DeprecatePlan
from cora.recipe.features.deprecate_plan.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `deprecate_plan` tool on the given MCP server."""

    @mcp.tool(
        name="deprecate_plan",
        description=(
            "Mark an existing plan as deprecated. Accepts both "
            "Defined and Versioned source states. Re-deprecating an "
            "already-Deprecated plan raises."
        ),
    )
    async def deprecate_plan_tool(  # pyright: ignore[reportUnusedFunction]
        plan_id: Annotated[
            UUID,
            Field(description="Target plan's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DeprecatePlan(plan_id=plan_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
