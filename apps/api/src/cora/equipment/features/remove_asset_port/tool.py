"""MCP tool for the `remove_asset_port` slice (Phase 5h)."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.aggregates.asset import PORT_NAME_MAX_LENGTH
from cora.equipment.features.remove_asset_port.command import RemoveAssetPort
from cora.equipment.features.remove_asset_port.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `remove_asset_port` tool on the given MCP server."""

    @mcp.tool(
        name="remove_asset_port",
        description=(
            "Remove a typed port from an existing Asset's port set "
            "by name. Strict-not-idempotent: rejects if no port with "
            "this name exists. Rejects when the asset is Decommissioned."
        ),
    )
    async def remove_asset_port_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
        port_name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=PORT_NAME_MAX_LENGTH,
                description="Name of the port to remove.",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            RemoveAssetPort(asset_id=asset_id, port_name=port_name),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
