"""MCP tool registration for the Supply BC.

`register_supply_tools(mcp, *, get_handlers)` registers each slice's
MCP tool on the shared FastMCP server. `get_handlers` is a callable
returning the `SupplyHandlers` bundle wired during the FastAPI
lifespan; it's invoked per tool call so the latest wiring is
always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.supply.features.get_supply import tool as get_supply_tool
from cora.supply.features.list_supplies import tool as list_supplies_tool
from cora.supply.features.mark_supply_available import tool as mark_supply_available_tool
from cora.supply.features.register_supply import tool as register_supply_tool
from cora.supply.wire import SupplyHandlers


def register_supply_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], SupplyHandlers],
) -> None:
    """Register every Supply slice's MCP tool on the FastMCP server."""
    register_supply_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_supply,
    )
    mark_supply_available_tool.register(
        mcp,
        get_handler=lambda: get_handlers().mark_supply_available,
    )
    get_supply_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_supply,
    )
    list_supplies_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_supplies,
    )
