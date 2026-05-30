"""MCP tool registration for the Federation BC.

`register_federation_tools(mcp, *, get_handlers)` registers each
slice's MCP tool on the shared FastMCP server. `get_handlers` is a
callable returning the `FederationHandlers` bundle wired during the
FastAPI lifespan; it is invoked per tool call so the latest wiring
is always used.

Stage 2b registers the five Permit lifecycle slice tools. The
Credential / Seal slice tools attach in Stage 2c.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.federation.features.activate_permit import tool as activate_permit_tool
from cora.federation.features.register_permit import tool as register_permit_tool
from cora.federation.features.resume_permit import tool as resume_permit_tool
from cora.federation.features.revoke_permit import tool as revoke_permit_tool
from cora.federation.features.suspend_permit import tool as suspend_permit_tool
from cora.federation.wire import FederationHandlers

federation_tools: list[object] = []


def register_federation_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], FederationHandlers],
) -> None:
    """Register every Federation slice's MCP tool on the FastMCP server."""
    register_permit_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_permit,
    )
    activate_permit_tool.register(
        mcp,
        get_handler=lambda: get_handlers().activate_permit,
    )
    suspend_permit_tool.register(
        mcp,
        get_handler=lambda: get_handlers().suspend_permit,
    )
    resume_permit_tool.register(
        mcp,
        get_handler=lambda: get_handlers().resume_permit,
    )
    revoke_permit_tool.register(
        mcp,
        get_handler=lambda: get_handlers().revoke_permit,
    )


__all__ = ["federation_tools", "register_federation_tools"]
