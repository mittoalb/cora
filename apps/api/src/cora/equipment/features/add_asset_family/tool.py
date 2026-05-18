"""MCP tool for the `add_asset_family` slice.

Mirror of `relocate_asset` MCP tool — single asset_id arg plus an
extra UUID arg (family_id). Domain / application errors
propagate to FastMCP, which wraps them as `isError: true`.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.features.add_asset_family.command import AddAssetFamily
from cora.equipment.features.add_asset_family.handler import Handler
from cora.infrastructure.observability import current_correlation_id


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
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
