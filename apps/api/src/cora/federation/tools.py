"""MCP tool registration for the Federation BC.

`register_federation_tools(mcp, *, get_handlers)` registers each
slice's MCP tool on the shared FastMCP server. `get_handlers` is a
callable returning the `FederationHandlers` bundle wired during the
FastAPI lifespan; it is invoked per tool call so the latest wiring
is always used.

Stage 2b registers the five Permit lifecycle slice tools.
Stage 2c-credential registers the five Credential lifecycle slice
tools. Stage 2c-seal registers the five Seal lifecycle slice
tools.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.federation.features.abort_credential_rotation import (
    tool as abort_credential_rotation_tool,
)
from cora.federation.features.activate_permit import tool as activate_permit_tool
from cora.federation.features.complete_credential_rotation import (
    tool as complete_credential_rotation_tool,
)
from cora.federation.features.complete_seal_republishing import (
    tool as complete_seal_republishing_tool,
)
from cora.federation.features.initialize_seal import tool as initialize_seal_tool
from cora.federation.features.register_credential import (
    tool as register_credential_tool,
)
from cora.federation.features.register_permit import tool as register_permit_tool
from cora.federation.features.resume_permit import tool as resume_permit_tool
from cora.federation.features.revoke_credential import tool as revoke_credential_tool
from cora.federation.features.revoke_permit import tool as revoke_permit_tool
from cora.federation.features.rotate_seal_online_key import (
    tool as rotate_seal_online_key_tool,
)
from cora.federation.features.sign_seal_pointer import tool as sign_seal_pointer_tool
from cora.federation.features.start_credential_rotation import (
    tool as start_credential_rotation_tool,
)
from cora.federation.features.start_seal_republishing import (
    tool as start_seal_republishing_tool,
)
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
    register_credential_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_credential,
    )
    start_credential_rotation_tool.register(
        mcp,
        get_handler=lambda: get_handlers().start_credential_rotation,
    )
    complete_credential_rotation_tool.register(
        mcp,
        get_handler=lambda: get_handlers().complete_credential_rotation,
    )
    abort_credential_rotation_tool.register(
        mcp,
        get_handler=lambda: get_handlers().abort_credential_rotation,
    )
    revoke_credential_tool.register(
        mcp,
        get_handler=lambda: get_handlers().revoke_credential,
    )
    initialize_seal_tool.register(
        mcp,
        get_handler=lambda: get_handlers().initialize_seal,
    )
    sign_seal_pointer_tool.register(
        mcp,
        get_handler=lambda: get_handlers().sign_seal_pointer,
    )
    rotate_seal_online_key_tool.register(
        mcp,
        get_handler=lambda: get_handlers().rotate_seal_online_key,
    )
    start_seal_republishing_tool.register(
        mcp,
        get_handler=lambda: get_handlers().start_seal_republishing,
    )
    complete_seal_republishing_tool.register(
        mcp,
        get_handler=lambda: get_handlers().complete_seal_republishing,
    )


__all__ = ["federation_tools", "register_federation_tools"]
