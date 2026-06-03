"""MCP tool for the `attach_asset_to_fixture` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.attach_asset_to_fixture.command import AttachAssetToFixture
from cora.equipment.features.attach_asset_to_fixture.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `attach_asset_to_fixture` tool on the given MCP server."""

    @mcp.tool(
        name="attach_asset_to_fixture",
        description=(
            "Bind an existing Asset to a registered Fixture by setting "
            "the Asset's fixture_id back-reference. The Fixture must "
            "have been registered with this Asset in its "
            "slot_asset_bindings (no phantom back-references). "
            "Strict-not-idempotent: re-attaching an Asset that already "
            "carries a fixture_id raises; detach first via "
            "detach_asset_from_fixture (B.6)."
        ),
    )
    async def attach_asset_to_fixture_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target Asset's id."),
        ],
        fixture_id: Annotated[
            UUID,
            Field(description="Target Fixture's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
