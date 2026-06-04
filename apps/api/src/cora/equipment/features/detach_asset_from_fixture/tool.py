"""MCP tool for the `detach_asset_from_fixture` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.equipment.features.detach_asset_from_fixture.command import DetachAssetFromFixture
from cora.equipment.features.detach_asset_from_fixture.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `detach_asset_from_fixture` tool on the given MCP server."""

    @mcp.tool(
        name="detach_asset_from_fixture",
        description=(
            "Clear an Asset's fixture_id back-reference (Asset becomes "
            "detached). Strict-not-idempotent: a second detach raises. "
            "The fixture_id argument is a defensive guard: if the Asset "
            "is actually attached to a different Fixture, the request "
            "is rejected. Allowed in any Asset lifecycle (including "
            "Decommissioned) to support cleanup workflows."
        ),
    )
    async def detach_asset_from_fixture_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target Asset's id."),
        ],
        fixture_id: Annotated[
            UUID,
            Field(
                description=("Fixture.id the Asset is expected to be currently attached to."),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DetachAssetFromFixture(asset_id=asset_id, fixture_id=fixture_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
