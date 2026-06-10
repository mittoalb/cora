"""MCP tool for the `bind_asset_to_facility` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.bind_asset_to_facility.command import BindAssetToFacility
from cora.equipment.features.bind_asset_to_facility.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.facility_code import FACILITY_CODE_MAX_LENGTH


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `bind_asset_to_facility` tool on the given MCP server."""

    @mcp.tool(
        name="bind_asset_to_facility",
        description=(
            "Bind an existing Asset to its owning Federation Facility "
            "via the cross-deployment slug (FacilityCode). Set-once: "
            "rejects with AssetFacilityCodeAlreadyAssignedError if the "
            "Asset already carries a facility_code (rebind path is "
            "decommission + re-register). Unknown facility_code raises "
            "AssetFacilityNotFoundError. Decommissioned-Facility "
            "binding is allowed."
        ),
    )
    async def bind_asset_to_facility_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target Asset's id."),
        ],
        facility_code: Annotated[
            str,
            Field(
                min_length=1,
                max_length=FACILITY_CODE_MAX_LENGTH,
                pattern=r"^[a-z0-9-]{1,32}$",
                description=(
                    "Cross-deployment Facility slug (for example "
                    "'aps', 'maxiv'). Lowercase ASCII alphanumeric plus "
                    "dash, 1-32 chars."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            BindAssetToFacility(asset_id=asset_id, facility_code=facility_code),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
