"""MCP tool for the `register_asset` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. MCP tools currently bypass header
extraction and use `SYSTEM_PRINCIPAL_ID` directly until the MCP
auth-flow phase lands (3j, deferred).

`level` accepts the StrEnum's string values; FastMCP's argument
schema enforces this. `parent_id` is `UUID | None`.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.aggregates.asset import ASSET_NAME_MAX_LENGTH, AssetLevel
from cora.equipment.features.register_asset.command import RegisterAsset
from cora.equipment.features.register_asset.handler import IdempotentHandler
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RegisterAssetOutput(BaseModel):
    """Structured output of the `register_asset` MCP tool."""

    asset_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_asset` tool on the given MCP server."""

    @mcp.tool(
        name="register_asset",
        description=(
            "Register a new physical equipment asset with the given "
            "name, hierarchical level, and parent. parent_id must be "
            "null for Enterprise-level roots; required for all others."
        ),
    )
    async def register_asset_tool(  # pyright: ignore[reportUnusedFunction]
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=ASSET_NAME_MAX_LENGTH,
                description="Display name for the new asset.",
            ),
        ],
        level: Annotated[
            AssetLevel,
            Field(
                description=(
                    "Hierarchical level: Enterprise (root, requires "
                    "null parent_id), Site, Area, Unit, Assembly, Device."
                ),
            ),
        ],
        parent_id: Annotated[
            UUID | None,
            Field(
                description=(
                    "Immediate parent in the hierarchy tree. Must be "
                    "null for Enterprise-level assets; required for "
                    "all others."
                ),
            ),
        ],
    ) -> RegisterAssetOutput:
        handler = get_handler()
        asset_id = await handler(
            RegisterAsset(name=name, level=level, parent_id=parent_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterAssetOutput(asset_id=asset_id)
