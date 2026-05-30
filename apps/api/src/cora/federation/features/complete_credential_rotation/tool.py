"""MCP tool for the `complete_credential_rotation` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. Returns the credential_id back so the caller
can chain follow-up tools (revoke / get_credential).
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.features.complete_credential_rotation.command import (
    CompleteCredentialRotation,
)
from cora.federation.features.complete_credential_rotation.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class CompleteCredentialRotationOutput(BaseModel):
    """Structured output of the `complete_credential_rotation` MCP tool."""

    credential_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `complete_credential_rotation` tool on the given MCP server."""

    @mcp.tool(
        name="complete_credential_rotation",
        description=(
            "Complete an in-flight credential rotation (Rotating -> Active). "
            "Single-source: requires the Credential to be in 'Rotating' status "
            "with pending refs populated; the pending secret_ref and "
            "public_material_ref are promoted to current. To discard the "
            "pending material instead, use 'abort_credential_rotation'."
        ),
    )
    async def complete_credential_rotation_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        credential_id: Annotated[
            UUID,
            Field(description="Target credential's id."),
        ],
    ) -> CompleteCredentialRotationOutput:
        handler = get_handler()
        await handler(
            CompleteCredentialRotation(credential_id=credential_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return CompleteCredentialRotationOutput(credential_id=credential_id)
