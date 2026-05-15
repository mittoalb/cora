"""MCP tool registration for the Operation BC.

`register_operation_tools(mcp, *, get_handlers)` registers each
slice's MCP tool on the shared FastMCP server. `get_handlers` is a
callable returning the `OperationHandlers` bundle wired during the
FastAPI lifespan; it's invoked per tool call so the latest wiring
is always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.operation.features.get_procedure import tool as get_procedure_tool
from cora.operation.features.register_procedure import tool as register_procedure_tool
from cora.operation.wire import OperationHandlers


def register_operation_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], OperationHandlers],
) -> None:
    """Register every Operation slice's MCP tool on the FastMCP server."""
    register_procedure_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_procedure,
    )
    get_procedure_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_procedure,
    )
