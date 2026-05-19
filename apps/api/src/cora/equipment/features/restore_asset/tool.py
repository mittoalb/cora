"""MCP tool for the `restore_asset` slice.

Mirror of `degrade_asset` MCP tool with target Nominal.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.features.restore_asset.command import RestoreAsset
from cora.equipment.features.restore_asset.handler import Handler
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id

_REASON_MAX_LENGTH = 500


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `restore_asset` tool on the given MCP server."""

    @mcp.tool(
        name="restore_asset",
        description=(
            "Mark an existing asset as Nominal (fully repaired). "
            "Target-state semantics: moves to Nominal from any source "
            "condition. Lifecycle is independent and unaffected. No-op "
            "when the asset is already Nominal. For partial repairs "
            "(Faulted -> Degraded), use degrade_asset, not this tool."
        ),
    )
    async def restore_asset_tool(  # pyright: ignore[reportUnusedFunction]
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
                    "Operator-supplied reason for the restore transition (audit-log breadcrumb)."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            RestoreAsset(asset_id=asset_id, reason=reason),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
