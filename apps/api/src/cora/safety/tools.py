"""MCP tool registration for the Safety BC."""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.safety.features.activate_clearance import tool as activate_clearance_tool
from cora.safety.features.approve_clearance import tool as approve_clearance_tool
from cora.safety.features.begin_review_clearance import tool as begin_review_clearance_tool
from cora.safety.features.get_clearance import tool as get_clearance_tool
from cora.safety.features.list_clearances import tool as list_clearances_tool
from cora.safety.features.record_review_step_clearance import (
    tool as record_review_step_clearance_tool,
)
from cora.safety.features.register_clearance import tool as register_clearance_tool
from cora.safety.features.reject_clearance import tool as reject_clearance_tool
from cora.safety.features.submit_clearance import tool as submit_clearance_tool
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
    list_clearances_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_clearances,
    )
    submit_clearance_tool.register(
        mcp,
        get_handler=lambda: get_handlers().submit_clearance,
    )
    begin_review_clearance_tool.register(
        mcp,
        get_handler=lambda: get_handlers().begin_review_clearance,
    )
    record_review_step_clearance_tool.register(
        mcp,
        get_handler=lambda: get_handlers().record_review_step_clearance,
    )
    approve_clearance_tool.register(
        mcp,
        get_handler=lambda: get_handlers().approve_clearance,
    )
    reject_clearance_tool.register(
        mcp,
        get_handler=lambda: get_handlers().reject_clearance,
    )
    activate_clearance_tool.register(
        mcp,
        get_handler=lambda: get_handlers().activate_clearance,
    )
