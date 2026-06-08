"""MCP tool registration for the Federation BC.

`register_federation_tools(mcp, *, get_handlers)` registers each
slice's MCP tool on the shared FastMCP server. `get_handlers` is a
callable returning the `FederationHandlers` bundle wired during the
FastAPI lifespan; it is invoked per tool call so the latest wiring
is always used.

Registered tools cover the five Permit lifecycle slices, the five
Credential lifecycle slices, the five Seal lifecycle slices, and the
six read-side slices (`list_permits` + `get_permit` +
`list_credentials` + `get_credential` + `list_seals` + `get_seal`).
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
from cora.federation.features.decommission_facility import (
    tool as decommission_facility_tool,
)
from cora.federation.features.define_permit import tool as define_permit_tool
from cora.federation.features.get_credential import tool as get_credential_tool
from cora.federation.features.get_permit import tool as get_permit_tool
from cora.federation.features.get_seal import tool as get_seal_tool
from cora.federation.features.initialize_seal import tool as initialize_seal_tool
from cora.federation.features.list_credentials import tool as list_credentials_tool
from cora.federation.features.list_permits import tool as list_permits_tool
from cora.federation.features.list_seals import tool as list_seals_tool
from cora.federation.features.register_credential import (
    tool as register_credential_tool,
)
from cora.federation.features.register_facility import tool as register_facility_tool
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
    define_permit_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_permit,
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
    register_facility_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_facility,
    )
    decommission_facility_tool.register(
        mcp,
        get_handler=lambda: get_handlers().decommission_facility,
    )
    list_permits_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_permits,
    )
    get_permit_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_permit,
    )
    list_credentials_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_credentials,
    )
    get_credential_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_credential,
    )
    list_seals_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_seals,
    )
    get_seal_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_seal,
    )


__all__ = ["federation_tools", "register_federation_tools"]
