"""MCP tool for the `add_asset_port` slice (Phase 5h)."""

from collections.abc import Callable
from typing import Annotated, Literal
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.aggregates.asset import (
    PORT_NAME_MAX_LENGTH,
    PORT_SIGNAL_TYPE_MAX_LENGTH,
    PortDirection,
)
from cora.equipment.features.add_asset_port.command import AddAssetPort
from cora.equipment.features.add_asset_port.handler import Handler
from cora.infrastructure.observability import current_correlation_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `add_asset_port` tool on the given MCP server."""

    @mcp.tool(
        name="add_asset_port",
        description=(
            "Add a typed port to an existing Asset's port set. Ports "
            "declare what connection points the equipment exposes "
            "(trigger_in, encoder_a, sync_clock, etc.). Plan.wiring "
            "will reference these by name to declare port-to-port "
            "connections."
        ),
    )
    async def add_asset_port_tool(  # pyright: ignore[reportUnusedFunction]
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
        port_name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=PORT_NAME_MAX_LENGTH,
                description="Port name unique within the Asset's scope.",
            ),
        ],
        direction: Annotated[
            Literal["Input", "Output"],
            Field(description="Port direction (PortDirection enum value)."),
        ],
        signal_type: Annotated[
            str,
            Field(
                min_length=1,
                max_length=PORT_SIGNAL_TYPE_MAX_LENGTH,
                description="Signal type free text (TTL / LVDS / Encoder / etc.).",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            AddAssetPort(
                asset_id=asset_id,
                port_name=port_name,
                direction=PortDirection(direction),
                signal_type=signal_type,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
