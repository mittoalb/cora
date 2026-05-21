"""MCP tool for the `add_asset_family` slice.

Mirror of `relocate_asset` MCP tool — single asset_id arg plus an
extra UUID arg (family_id). Domain / application errors
propagate to FastMCP, which wraps them as `isError: true`.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.add_asset_family.command import AddAssetFamily
from cora.equipment.features.add_asset_family.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `add_asset_family` tool on the given MCP server."""

    @mcp.tool(
        name="add_asset_family",
        description=(
            "Add a Family to an existing asset's family set. "
            "Decommissioned assets cannot accept new families; "
            "re-adding a family already in the set raises."
        ),
    )
    async def add_asset_family_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
        family_id: Annotated[
            UUID,
            Field(
                description=("Family id to add. Eventual-consistency: existence is NOT verified."),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            AddAssetFamily(asset_id=asset_id, family_id=family_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
