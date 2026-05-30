"""MCP tool for the `revoke_credential` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. Mirrors `revoke_permit`'s tool surface; the
optional `reason` argument is accepted but not persisted on the
`CredentialRevoked` event today.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.features.revoke_credential.command import RevokeCredential
from cora.federation.features.revoke_credential.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RevokeCredentialOutput(BaseModel):
    """Structured output of the `revoke_credential` MCP tool."""

    credential_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `revoke_credential` tool on the given MCP server."""

    @mcp.tool(
        name="revoke_credential",
        description=(
            "Revoke a Credential (terminal: any non-Revoked status -> Revoked). "
            "Accepts Active or Rotating; revocation past expires_at is also "
            "valid. Strict-not-idempotent: revoking an already-Revoked "
            "credential raises. Once Revoked the credential cannot be revived; "
            "mint a fresh one via register_credential if the federation flow "
            "must resume. Emits a paired Decision-BC audit atomically."
        ),
    )
    async def revoke_credential_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        credential_id: Annotated[
            UUID,
            Field(description="Target credential's id."),
        ],
        reason: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Optional free-text operator intent for the revoke. "
                    "Accepted but not persisted on the CredentialRevoked event "
                    "today; reserved for a future audit-narrative wiring."
                ),
            ),
        ] = None,
    ) -> RevokeCredentialOutput:
        handler = get_handler()
        await handler(
            RevokeCredential(credential_id=credential_id, reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RevokeCredentialOutput(credential_id=credential_id)
