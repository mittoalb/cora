"""MCP tool for the `update_asset_settings` slice.

Mirror of the HTTP route: the tool accepts `asset_id` and a
`settings_patch` dict applied with RFC 7396 merge semantics. Domain
errors propagate to FastMCP as `isError: true`.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.features.update_asset_settings.command import UpdateAssetSettings
from cora.equipment.features.update_asset_settings.handler import Handler
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `update_asset_settings` tool on the given MCP server."""

    @mcp.tool(
        name="update_asset_settings",
        description=(
            "Update an existing asset's settings dict using RFC 7396 "
            "JSON Merge Patch semantics: keys with non-null values "
            "set/replace; keys with null delete; absent keys are "
            "preserved. The merged result is validated against the "
            "union of the asset's currently-assigned Capabilities' "
            "settings_schemas."
        ),
    )
    async def update_asset_settings_tool(  # pyright: ignore[reportUnusedFunction]
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
        settings_patch: Annotated[
            dict[str, Any],
            Field(
                description=("Partial settings dict applied with RFC 7396 merge semantics."),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            UpdateAssetSettings(asset_id=asset_id, settings_patch=settings_patch),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
