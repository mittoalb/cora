"""MCP tool for the `install_asset` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.install_asset.command import InstallAsset
from cora.equipment.features.install_asset.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    @mcp.tool(
        name="install_asset",
        description=(
            "Install an Asset specimen into a Mount slot. Rejected if "
            "the Asset does not exist (AssetNotFoundForMountError), the "
            "Mount is Decommissioned (MountCannotUpdateError), or the "
            "slot is already occupied (MountAlreadyOccupiedError; "
            "uninstall first, no implicit eviction)."
        ),
    )
    async def install_asset_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        mount_id: Annotated[UUID, Field(description="The target Mount slot.")],
        asset_id: Annotated[UUID, Field(description="The Asset specimen to install.")],
    ) -> None:
        handler = get_handler()
        await handler(
            InstallAsset(mount_id=mount_id, asset_id=asset_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
