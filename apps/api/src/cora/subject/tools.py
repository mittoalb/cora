"""MCP tool registration for the Subject BC.

`register_subject_tools(mcp, *, get_handlers)` registers each slice's
MCP tool on the shared FastMCP server. `get_handlers` is a callable
returning the `SubjectHandlers` bundle wired during the FastAPI
lifespan; it's invoked per tool call so the latest wiring is always
used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.subject.features.mount_subject import tool as mount_subject_tool
from cora.subject.features.register_subject import tool as register_subject_tool
from cora.subject.wire import SubjectHandlers


def register_subject_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], SubjectHandlers],
) -> None:
    """Register every Subject slice's MCP tool on the FastMCP server."""
    register_subject_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_subject,
    )
    mount_subject_tool.register(
        mcp,
        get_handler=lambda: get_handlers().mount_subject,
    )
