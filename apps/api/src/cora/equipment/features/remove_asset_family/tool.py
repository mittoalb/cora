"""MCP tool for the `remove_asset_family` slice.

Mirror of `add_asset_family` MCP tool.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.remove_asset_family.command import RemoveAssetFamily
from cora.equipment.features.remove_asset_family.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `remove_asset_family` tool on the given MCP server."""

    @mcp.tool(
        name="remove_asset_family",
        description=(
            "Remove a Family from an existing asset's family set. "
            "Decommissioned assets cannot have families removed; "
            "removing a family not in the set raises."
        ),
    )
    async def remove_asset_family_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
        family_id: Annotated[
            UUID,
            Field(description="Family id to remove."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            RemoveAssetFamily(asset_id=asset_id, family_id=family_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
