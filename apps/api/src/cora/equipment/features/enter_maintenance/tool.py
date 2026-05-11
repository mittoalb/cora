"""MCP tool for the `enter_maintenance` slice.

Mirror of `activate_asset` MCP tool. Single asset_id argument,
no structured content on success. Domain / application errors
propagate to FastMCP, which wraps them as `isError: true`.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.features.enter_maintenance.command import EnterMaintenance
from cora.equipment.features.enter_maintenance.handler import Handler
from cora.infrastructure.observability import current_correlation_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `enter_maintenance` tool on the given MCP server."""

    @mcp.tool(
        name="enter_maintenance",
        description="Take an existing (Active) asset out of service for maintenance.",
    )
    async def enter_maintenance_tool(  # pyright: ignore[reportUnusedFunction]
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            EnterMaintenance(asset_id=asset_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
