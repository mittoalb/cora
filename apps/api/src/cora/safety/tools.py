"""MCP tool registration for the Safety BC.

`register_safety_tools(mcp, *, get_handlers)` registers each slice's
MCP tool on the shared FastMCP server. `get_handlers` is a callable
returning the `SafetyHandlers` bundle wired during the FastAPI
lifespan; it's invoked per tool call so the latest wiring is always
used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.safety.features.get_clearance import tool as get_clearance_tool
from cora.safety.features.register_clearance import tool as register_clearance_tool
from cora.safety.wire import SafetyHandlers


def register_safety_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], SafetyHandlers],
) -> None:
    """Register every Safety slice's MCP tool on the FastMCP server."""
    register_clearance_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_clearance,
    )
    get_clearance_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_clearance,
    )
