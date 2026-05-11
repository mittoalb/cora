"""MCP tool registration for the Run BC.

`register_run_tools(mcp, *, get_handlers)` registers each slice's
MCP tool on the shared FastMCP server. `get_handlers` is a callable
returning the `RunHandlers` bundle wired during the FastAPI lifespan;
it's invoked per tool call so the latest wiring is always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.run.features.get_run import tool as get_run_tool
from cora.run.features.start_run import tool as start_run_tool
from cora.run.wire import RunHandlers


def register_run_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], RunHandlers],
) -> None:
    """Register every Run slice's MCP tool on the FastMCP server."""
    start_run_tool.register(
        mcp,
        get_handler=lambda: get_handlers().start_run,
    )
    get_run_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_run,
    )
