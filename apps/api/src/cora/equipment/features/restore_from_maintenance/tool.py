"""MCP tool for the `restore_from_maintenance` slice.

Mirror of `enter_maintenance` MCP tool. Single asset_id argument,
no structured content on success. Domain / application errors
propagate to FastMCP, which wraps them as `isError: true`.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.features.restore_from_maintenance.command import RestoreFromMaintenance
from cora.equipment.features.restore_from_maintenance.handler import Handler
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `restore_from_maintenance` tool on the given MCP server."""

    @mcp.tool(
        name="restore_from_maintenance",
        description="Return an existing (Maintenance) asset to active service.",
    )
    async def restore_from_maintenance_tool(  # pyright: ignore[reportUnusedFunction]
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            RestoreFromMaintenance(asset_id=asset_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
