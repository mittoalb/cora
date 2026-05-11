"""MCP tool for the `deprecate_capability` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.features.deprecate_capability.command import DeprecateCapability
from cora.equipment.features.deprecate_capability.handler import Handler
from cora.infrastructure.observability import current_correlation_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `deprecate_capability` tool on the given MCP server."""

    @mcp.tool(
        name="deprecate_capability",
        description=(
            "Mark an existing capability as deprecated. Accepts both "
            "Defined and Versioned source states. Re-deprecating an "
            "already-Deprecated capability raises."
        ),
    )
    async def deprecate_capability_tool(  # pyright: ignore[reportUnusedFunction]
        capability_id: Annotated[
            UUID,
            Field(description="Target capability's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DeprecateCapability(capability_id=capability_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
