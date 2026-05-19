"""MCP tool for the `deprecate_family` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.features.deprecate_family.command import DeprecateFamily
from cora.equipment.features.deprecate_family.handler import Handler
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `deprecate_family` tool on the given MCP server."""

    @mcp.tool(
        name="deprecate_family",
        description=(
            "Mark an existing family as deprecated. Accepts both "
            "Defined and Versioned source states. Re-deprecating an "
            "already-Deprecated family raises."
        ),
    )
    async def deprecate_family_tool(  # pyright: ignore[reportUnusedFunction]
        family_id: Annotated[
            UUID,
            Field(description="Target family's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DeprecateFamily(family_id=family_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
