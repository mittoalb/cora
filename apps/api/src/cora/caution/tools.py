"""MCP tool registration for the Caution BC.

`register_caution_tools(mcp, *, get_handlers)` registers each slice's
MCP tool on the shared FastMCP server. `get_handlers` is a callable
returning the `CautionHandlers` bundle wired during the FastAPI
lifespan; it's invoked per tool call so the latest wiring is
always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.caution.features.get_caution import tool as get_caution_tool
from cora.caution.features.list_cautions import tool as list_cautions_tool
from cora.caution.features.register_caution import tool as register_caution_tool
from cora.caution.features.retire_caution import tool as retire_caution_tool
from cora.caution.features.supersede_caution import tool as supersede_caution_tool
from cora.caution.wire import CautionHandlers


def register_caution_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], CautionHandlers],
) -> None:
    """Register every Caution slice's MCP tool on the FastMCP server."""
    register_caution_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_caution,
    )
    supersede_caution_tool.register(
        mcp,
        get_handler=lambda: get_handlers().supersede_caution,
    )
    retire_caution_tool.register(
        mcp,
        get_handler=lambda: get_handlers().retire_caution,
    )
    get_caution_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_caution,
    )
    list_cautions_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_cautions,
    )
