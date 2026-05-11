"""MCP tool for the `get_asset` query slice.

Surfaces the same handler the REST route uses. Returns a structured
AssetOutput on hit. On miss raises an exception that FastMCP wraps
as `isError: true` with a text diagnostic — matches the REST 404
behaviour in MCP's error idiom (LLM consumers get a clear "asset
not found" message rather than null structuredContent they have to
interpret).
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.aggregates.asset import ASSET_NAME_MAX_LENGTH
from cora.equipment.features.get_asset.handler import Handler
from cora.equipment.features.get_asset.query import GetAsset
from cora.infrastructure.observability import current_correlation_id


class AssetOutput(BaseModel):
    """Structured output of the `get_asset` MCP tool."""

    id: UUID
    name: str = Field(..., max_length=ASSET_NAME_MAX_LENGTH)
    level: str
    parent_id: UUID | None
    lifecycle: str


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_asset` tool on the given MCP server."""

    @mcp.tool(
        name="get_asset",
        description="Read the current state of an existing asset by id.",
    )
    async def get_asset_tool(  # pyright: ignore[reportUnusedFunction]
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
    ) -> AssetOutput:
        handler = get_handler()
        asset = await handler(
            GetAsset(asset_id=asset_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        if asset is None:
            msg = f"Asset {asset_id} not found"
            raise ValueError(msg)
        return AssetOutput(
            id=asset.id,
            name=asset.name.value,
            level=asset.level.value,
            parent_id=asset.parent_id,
            lifecycle=asset.lifecycle.value,
        )
