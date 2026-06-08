"""MCP tool for the `initialize_seal` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. Returns the deterministic Seal stream UUID
so the caller can address the stream directly when polling read-side
surfaces; the singleton's identity (`facility_code`) is echoed back
for correlation.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.features.initialize_seal.command import InitializeSeal
from cora.federation.features.initialize_seal.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class InitializeSealOutput(BaseModel):
    """Structured output of the `initialize_seal` MCP tool."""

    seal_stream_id: UUID
    facility_code: str


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `initialize_seal` tool on the given MCP server."""

    @mcp.tool(
        name="initialize_seal",
        description=(
            "Initialize the per-facility Seal singleton (genesis; lands in "
            "Live). Atomically emits a DecisionRegistered audit on the "
            "Decision stream. Required: facility_code, online_credential_id, "
            "offline_credential_id. online_credential_id MUST differ from "
            "offline_credential_id (key-separation invariant)."
        ),
    )
    async def initialize_seal_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        facility_code: Annotated[
            str,
            Field(
                min_length=1,
                description=(
                    "Cross-deployment convergent facility slug this Seal "
                    "binds to. Validated against the FacilityCode VO pattern "
                    "(lowercase ASCII alphanumeric and dash, 1-32 chars) at "
                    "the handler edge. Doubles as the singleton identity "
                    "(one Seal per facility)."
                ),
            ),
        ],
        online_credential_id: Annotated[
            UUID,
            Field(
                description=(
                    "Credential.id of the warm signing key "
                    "(purpose SealOnlineSigning). Must differ from offline_credential_id."
                ),
            ),
        ],
        offline_credential_id: Annotated[
            UUID,
            Field(
                description=(
                    "Credential.id of the cold root key "
                    "(purpose SealOfflineRoot). Must differ from online_credential_id."
                ),
            ),
        ],
    ) -> InitializeSealOutput:
        handler = get_handler()
        stream_id = await handler(
            InitializeSeal(
                facility_code=facility_code,
                online_credential_id=online_credential_id,
                offline_credential_id=offline_credential_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return InitializeSealOutput(seal_stream_id=stream_id, facility_code=facility_code)
