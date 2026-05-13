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
from cora.equipment.features.add_asset_capability import (
    tool as add_asset_capability_tool,
)
from cora.equipment.features.decommission_asset import tool as decommission_asset_tool
from cora.equipment.features.define_capability import tool as define_capability_tool
from cora.equipment.features.degrade_asset import tool as degrade_asset_tool
from cora.equipment.features.deprecate_capability import (
    tool as deprecate_capability_tool,
)
from cora.equipment.features.enter_maintenance import tool as enter_maintenance_tool
from cora.equipment.features.fault_asset import tool as fault_asset_tool
from cora.equipment.features.get_asset import tool as get_asset_tool
from cora.equipment.features.get_capability import tool as get_capability_tool
from cora.equipment.features.list_assets import tool as list_assets_tool
from cora.equipment.features.list_capabilities import tool as list_capabilities_tool
from cora.equipment.features.register_asset import tool as register_asset_tool
from cora.equipment.features.relocate_asset import tool as relocate_asset_tool
from cora.equipment.features.remove_asset_capability import (
    tool as remove_asset_capability_tool,
)
from cora.equipment.features.restore_asset import tool as restore_asset_tool
from cora.equipment.features.restore_from_maintenance import (
    tool as restore_from_maintenance_tool,
)
from cora.equipment.features.update_capability_schema import (
    tool as update_capability_schema_tool,
)
from cora.equipment.features.version_capability import tool as version_capability_tool
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
    version_capability_tool.register(
        mcp,
        get_handler=lambda: get_handlers().version_capability,
    )
    deprecate_capability_tool.register(
        mcp,
        get_handler=lambda: get_handlers().deprecate_capability,
    )
    update_capability_schema_tool.register(
        mcp,
        get_handler=lambda: get_handlers().update_capability_schema,
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
    relocate_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().relocate_asset,
    )
    enter_maintenance_tool.register(
        mcp,
        get_handler=lambda: get_handlers().enter_maintenance,
    )
    restore_from_maintenance_tool.register(
        mcp,
        get_handler=lambda: get_handlers().restore_from_maintenance,
    )
    add_asset_capability_tool.register(
        mcp,
        get_handler=lambda: get_handlers().add_asset_capability,
    )
    remove_asset_capability_tool.register(
        mcp,
        get_handler=lambda: get_handlers().remove_asset_capability,
    )
    degrade_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().degrade_asset,
    )
    fault_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().fault_asset,
    )
    restore_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().restore_asset,
    )
    get_asset_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_asset,
    )
    list_assets_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_assets,
    )
    list_capabilities_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_capabilities,
    )
