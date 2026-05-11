"""MCP tool for the `activate_asset` slice.

Mirror of Subject's update-style MCP tools. Single asset_id
argument, no structured content on success. Domain / application
errors propagate to FastMCP, which wraps them as `isError: true`.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.features.activate_asset.command import ActivateAsset
from cora.equipment.features.activate_asset.handler import Handler
from cora.infrastructure.observability import current_correlation_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `activate_asset` tool on the given MCP server."""

    @mcp.tool(
        name="activate_asset",
        description="Activate an existing (Commissioned) asset, putting it into service.",
    )
    async def activate_asset_tool(  # pyright: ignore[reportUnusedFunction]
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            ActivateAsset(asset_id=asset_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
