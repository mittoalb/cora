"""MCP tool registration for the Equipment BC.

`register_equipment_tools(mcp, *, get_handlers)` registers each
slice's MCP tool on the shared FastMCP server. `get_handlers` is a
callable returning the `EquipmentHandlers` bundle wired during the
FastAPI lifespan; it's invoked per tool call so the latest wiring
is always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.equipment.features.activate_asset import tool as activate_asset_tool
from cora.equipment.features.decommission_asset import tool as decommission_asset_tool
from cora.equipment.features.define_capability import tool as define_capability_tool
from cora.equipment.features.get_capability import tool as get_capability_tool
from cora.equipment.features.register_asset import tool as register_asset_tool
from cora.equipment.wire import EquipmentHandlers


def register_equipment_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], EquipmentHandlers],
) -> None:
    """Register every Equipment slice's MCP tool on the FastMCP server."""
    define_capability_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_capability,
    )
    get_capability_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_capability,
    )
    register_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_asset,
    )
    activate_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().activate_asset,
    )
    decommission_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().decommission_asset,
    )
