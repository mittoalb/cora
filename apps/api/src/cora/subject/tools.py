"""MCP tool registration for the Subject BC.

`register_subject_tools(mcp, *, get_handlers)` registers each slice's
MCP tool on the shared FastMCP server. `get_handlers` is a callable
returning the `SubjectHandlers` bundle wired during the FastAPI
lifespan; it's invoked per tool call so the latest wiring is always
used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.subject.features.discard_subject import tool as discard_subject_tool
from cora.subject.features.dismount_subject import tool as dismount_subject_tool
from cora.subject.features.get_subject import tool as get_subject_tool
from cora.subject.features.list_subjects import tool as list_subjects_tool
from cora.subject.features.measure_subject import tool as measure_subject_tool
from cora.subject.features.mount_subject import tool as mount_subject_tool
from cora.subject.features.register_subject import tool as register_subject_tool
from cora.subject.features.remove_subject import tool as remove_subject_tool
from cora.subject.features.return_subject import tool as return_subject_tool
from cora.subject.features.store_subject import tool as store_subject_tool
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
    dismount_subject_tool.register(
        mcp,
        get_handler=lambda: get_handlers().dismount_subject,
    )
    measure_subject_tool.register(
        mcp,
        get_handler=lambda: get_handlers().measure_subject,
    )
    remove_subject_tool.register(
        mcp,
        get_handler=lambda: get_handlers().remove_subject,
    )
    return_subject_tool.register(
        mcp,
        get_handler=lambda: get_handlers().return_subject,
    )
    store_subject_tool.register(
        mcp,
        get_handler=lambda: get_handlers().store_subject,
    )
    discard_subject_tool.register(
        mcp,
        get_handler=lambda: get_handlers().discard_subject,
    )
    get_subject_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_subject,
    )
    list_subjects_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_subjects,
    )
