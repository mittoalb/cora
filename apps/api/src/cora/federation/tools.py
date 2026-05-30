"""MCP tool registration for the Federation BC.

`register_federation_tools(mcp, *, get_handlers)` registers each
slice's MCP tool on the shared FastMCP server. `get_handlers` is a
callable returning the `FederationHandlers` bundle wired during the
FastAPI lifespan; it is invoked per tool call so the latest wiring
is always used.

Stage 2a is a no-op: the per-slice MCP tools (Permit / Credential /
Seal) attach in Stage 2b/2c when their handlers exist.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.federation.wire import FederationHandlers

federation_tools: list[object] = []


def register_federation_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], FederationHandlers],
) -> None:
    """Register every Federation slice's MCP tool on the FastMCP server."""
    _ = mcp
    _ = get_handlers


__all__ = ["federation_tools", "register_federation_tools"]
