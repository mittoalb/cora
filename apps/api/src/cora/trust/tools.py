"""MCP tool registration for the Trust BC.

`register_trust_tools(mcp, *, get_handlers)` registers each slice's MCP
tool on the shared FastMCP server. `get_handlers` is a callable returning
the `TrustHandlers` bundle wired during the FastAPI lifespan; it's
invoked per tool call so the latest wiring is always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.trust.features.abort_visit import tool as abort_visit_tool
from cora.trust.features.arrive_visit import tool as arrive_visit_tool
from cora.trust.features.cancel_visit import tool as cancel_visit_tool
from cora.trust.features.complete_visit import tool as complete_visit_tool
from cora.trust.features.define_conduit import tool as define_conduit_tool
from cora.trust.features.define_policy import tool as define_policy_tool
from cora.trust.features.define_surface import tool as define_surface_tool
from cora.trust.features.define_zone import tool as define_zone_tool
from cora.trust.features.evaluate_policy import tool as evaluate_policy_tool
from cora.trust.features.get_surface import tool as get_surface_tool
from cora.trust.features.hold_visit import tool as hold_visit_tool
from cora.trust.features.list_conduits import tool as list_conduits_tool
from cora.trust.features.list_permissions import tool as list_permissions_tool
from cora.trust.features.list_policies import tool as list_policies_tool
from cora.trust.features.list_zones import tool as list_zones_tool
from cora.trust.features.register_visit import tool as register_visit_tool
from cora.trust.features.resume_visit import tool as resume_visit_tool
from cora.trust.features.start_visit import tool as start_visit_tool
from cora.trust.features.void_visit import tool as void_visit_tool
from cora.trust.wire import TrustHandlers


def register_trust_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], TrustHandlers],
) -> None:
    """Register every Trust slice's MCP tool on the FastMCP server."""
    define_zone_tool.register(mcp, get_handler=lambda: get_handlers().define_zone)
    define_conduit_tool.register(mcp, get_handler=lambda: get_handlers().define_conduit)
    define_policy_tool.register(mcp, get_handler=lambda: get_handlers().define_policy)
    define_surface_tool.register(mcp, get_handler=lambda: get_handlers().define_surface)
    evaluate_policy_tool.register(mcp, get_handler=lambda: get_handlers().evaluate_policy)
    get_surface_tool.register(mcp, get_handler=lambda: get_handlers().get_surface)
    list_zones_tool.register(mcp, get_handler=lambda: get_handlers().list_zones)
    list_conduits_tool.register(mcp, get_handler=lambda: get_handlers().list_conduits)
    list_policies_tool.register(mcp, get_handler=lambda: get_handlers().list_policies)
    list_permissions_tool.register(mcp, get_handler=lambda: get_handlers().list_permissions)
    # Visit lifecycle tools (Phase beta).
    register_visit_tool.register(mcp, get_handler=lambda: get_handlers().register_visit)
    arrive_visit_tool.register(mcp, get_handler=lambda: get_handlers().arrive_visit)
    start_visit_tool.register(mcp, get_handler=lambda: get_handlers().start_visit)
    hold_visit_tool.register(mcp, get_handler=lambda: get_handlers().hold_visit)
    resume_visit_tool.register(mcp, get_handler=lambda: get_handlers().resume_visit)
    complete_visit_tool.register(mcp, get_handler=lambda: get_handlers().complete_visit)
    cancel_visit_tool.register(mcp, get_handler=lambda: get_handlers().cancel_visit)
    abort_visit_tool.register(mcp, get_handler=lambda: get_handlers().abort_visit)
    void_visit_tool.register(mcp, get_handler=lambda: get_handlers().void_visit)
