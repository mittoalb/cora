"""MCP tool for the `exit_asset_maintenance` slice.

Mirror of `enter_asset_maintenance` MCP tool. Single asset_id argument,
no structured content on success. Domain / application errors
propagate to FastMCP, which wraps them as `isError: true`.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.exit_asset_maintenance.command import ExitAssetMaintenance
from cora.equipment.features.exit_asset_maintenance.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `exit_asset_maintenance` tool on the given MCP server."""

    @mcp.tool(
        name="exit_asset_maintenance",
        description="Return an existing (Maintenance) asset to active service.",
    )
    async def exit_asset_maintenance_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            ExitAssetMaintenance(asset_id=asset_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
