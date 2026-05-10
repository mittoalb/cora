"""MCP tool registration for the Trust BC.

`register_trust_tools(mcp, *, get_handlers)` registers each slice's MCP
tool on the shared FastMCP server. `get_handlers` is a callable returning
the `TrustHandlers` bundle wired during the FastAPI lifespan; it's
invoked per tool call so the latest wiring is always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.trust.features.define_conduit import tool as define_conduit_tool
from cora.trust.features.define_policy import tool as define_policy_tool
from cora.trust.features.define_zone import tool as define_zone_tool
from cora.trust.features.evaluate_policy import tool as evaluate_policy_tool
from cora.trust.wire import TrustHandlers


def register_trust_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], TrustHandlers],
) -> None:
    """Register every Trust slice's MCP tool on the FastMCP server."""
    define_zone_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_zone,
    )
    define_conduit_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_conduit,
    )
    define_policy_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_policy,
    )
    evaluate_policy_tool.register(
        mcp,
        get_handler=lambda: get_handlers().evaluate_policy,
    )
