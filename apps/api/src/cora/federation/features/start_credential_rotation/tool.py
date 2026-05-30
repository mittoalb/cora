"""MCP tool for the `start_credential_rotation` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. Returns the credential_id back so the caller
can chain follow-up tools (complete_credential_rotation /
abort_credential_rotation / get_credential).
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.features.start_credential_rotation.command import (
    StartCredentialRotation,
)
from cora.federation.features.start_credential_rotation.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class StartCredentialRotationOutput(BaseModel):
    """Structured output of the `start_credential_rotation` MCP tool."""

    credential_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `start_credential_rotation` tool on the given MCP server."""

    @mcp.tool(
        name="start_credential_rotation",
        description=(
            "Start a rotation against an Active credential (Active -> Rotating). "
            "Single-source: requires the Credential to be in 'Active' status. "
            "The supplied new_secret_ref and new_public_material_ref are "
            "opaque pointers to material already provisioned in the "
            "SecretStore adapter; raw secret bytes never cross this boundary. "
            "Strict-not-idempotent: starting against a Rotating or Revoked "
            "credential raises, as does supplying a new_secret_ref equal to "
            "the current secret_ref. To finalise, call "
            "complete_credential_rotation; to discard, call "
            "abort_credential_rotation."
        ),
    )
    async def start_credential_rotation_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        credential_id: Annotated[
            UUID,
            Field(description="Target credential's id."),
        ],
        new_secret_ref: Annotated[
            str,
            Field(
                min_length=1,
                description=(
                    "Opaque pointer to the pending secret material. Must "
                    "differ from the credential's current secret_ref."
                ),
            ),
        ],
        new_public_material_ref: Annotated[
            str | None,
            Field(
                description=(
                    "Optional opaque pointer to the pending public "
                    "counterpart. None when the purpose is symmetric or "
                    "the public half lives elsewhere."
                ),
            ),
        ] = None,
    ) -> StartCredentialRotationOutput:
        handler = get_handler()
        await handler(
            StartCredentialRotation(
                credential_id=credential_id,
                new_secret_ref=new_secret_ref,
                new_public_material_ref=new_public_material_ref,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return StartCredentialRotationOutput(credential_id=credential_id)
