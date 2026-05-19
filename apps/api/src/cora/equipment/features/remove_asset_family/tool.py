"""MCP tool for the `remove_asset_family` slice.

Mirror of `add_asset_family` MCP tool.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.features.remove_asset_family.command import RemoveAssetFamily
from cora.equipment.features.remove_asset_family.handler import Handler
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
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
