"""MCP tool registration for the Safety BC."""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.safety.features.activate_clearance import tool as activate_clearance_tool
from cora.safety.features.amend_clearance import tool as amend_clearance_tool
from cora.safety.features.append_clearance_review_step import (
    tool as append_clearance_review_step_tool,
)
from cora.safety.features.approve_clearance import tool as approve_clearance_tool
from cora.safety.features.expire_clearance import tool as expire_clearance_tool
from cora.safety.features.get_clearance import tool as get_clearance_tool
from cora.safety.features.list_clearances import tool as list_clearances_tool
from cora.safety.features.register_clearance import tool as register_clearance_tool
from cora.safety.features.reject_clearance import tool as reject_clearance_tool
from cora.safety.features.start_clearance_review import tool as start_clearance_review_tool
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
    start_clearance_review_tool.register(
        mcp,
        get_handler=lambda: get_handlers().start_clearance_review,
    )
    append_clearance_review_step_tool.register(
        mcp,
        get_handler=lambda: get_handlers().append_clearance_review_step,
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
    expire_clearance_tool.register(
        mcp,
        get_handler=lambda: get_handlers().expire_clearance,
    )
    amend_clearance_tool.register(
        mcp,
        get_handler=lambda: get_handlers().amend_clearance,
    )
