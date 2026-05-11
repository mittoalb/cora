"""MCP tool for the `relocate_asset` slice.

Mirror of `activate_asset` / `decommission_asset` MCP tools but
with two arguments (`to_parent_id`, `reason`). Domain / application
errors propagate to FastMCP, which wraps them as `isError: true`.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.features.relocate_asset.command import RelocateAsset
from cora.equipment.features.relocate_asset.handler import Handler
from cora.infrastructure.observability import current_correlation_id

_REASON_MAX_LENGTH = 500


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `relocate_asset` tool on the given MCP server."""

    @mcp.tool(
        name="relocate_asset",
        description=(
            "Move an existing asset under a new parent in the hierarchy. "
            "Enterprise-level assets are roots and cannot be relocated; "
            "Decommissioned assets are retired and cannot be moved."
        ),
    )
    async def relocate_asset_tool(  # pyright: ignore[reportUnusedFunction]
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
        to_parent_id: Annotated[
            UUID,
            Field(
                description=(
                    "New parent in the hierarchy tree. Must be non-null. "
                    "Eventual-consistency: parent's existence is NOT verified."
                ),
            ),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=_REASON_MAX_LENGTH,
                description=("Operator-supplied reason for the relocation (audit-log breadcrumb)."),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            RelocateAsset(asset_id=asset_id, to_parent_id=to_parent_id, reason=reason),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
