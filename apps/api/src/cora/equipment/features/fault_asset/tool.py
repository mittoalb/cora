"""MCP tool for the `fault_asset` slice.

Mirror of `degrade_asset` MCP tool with target Faulted.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.features.fault_asset.command import FaultAsset
from cora.equipment.features.fault_asset.handler import Handler
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id

_REASON_MAX_LENGTH = 500


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `fault_asset` tool on the given MCP server."""

    @mcp.tool(
        name="fault_asset",
        description=(
            "Mark an existing asset as Faulted (does not work, requires "
            "repair). Target-state semantics: moves to Faulted from any "
            "source condition. Lifecycle is independent and unaffected. "
            "No-op when the asset is already Faulted."
        ),
    )
    async def fault_asset_tool(  # pyright: ignore[reportUnusedFunction]
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=_REASON_MAX_LENGTH,
                description=(
                    "Operator-supplied reason for the fault transition (audit-log breadcrumb)."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            FaultAsset(asset_id=asset_id, reason=reason),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
