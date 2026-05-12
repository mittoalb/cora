"""MCP tool registration for the Decision BC."""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.decision.features.get_decision import tool as get_decision_tool
from cora.decision.features.register_decision import tool as register_decision_tool
from cora.decision.wire import DecisionHandlers


def register_decision_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], DecisionHandlers],
) -> None:
    """Register every Decision slice's MCP tool on the FastMCP server."""
    register_decision_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_decision,
    )
    get_decision_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_decision,
    )
