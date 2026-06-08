"""MCP tool for the `register_credential` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. The `purpose` argument is the closed
`CredentialPurpose` StrEnum (six arms). `secret_ref` is a
pre-existing opaque pointer; raw secret bytes NEVER cross this wire
per AH#6 of the locked design.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.aggregates.credential import CredentialPurpose
from cora.federation.features.register_credential.command import RegisterCredential
from cora.federation.features.register_credential.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RegisterCredentialOutput(BaseModel):
    """Structured output of the `register_credential` MCP tool."""

    credential_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_credential` tool on the given MCP server."""

    @mcp.tool(
        name="register_credential",
        description=(
            "Register a new federation Credential (genesis; lands in Active). "
            "Atomically emits a DecisionRegistered audit on the Decision "
            "stream. Required: facility_code, audience, purpose, secret_ref. "
            "Optional: public_material_ref, expires_at. `secret_ref` is an "
            "opaque pointer (URI / KMS ARN / vault path); raw secret bytes "
            "must be landed in the SecretStore adapter BEFORE invoking this "
            "tool."
        ),
    )
    async def register_credential_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        facility_code: Annotated[
            str,
            Field(
                min_length=1,
                description="Cross-deployment convergent facility slug this credential binds to.",
            ),
        ],
        audience: Annotated[
            str,
            Field(min_length=1, description="Opaque scope (peer / endpoint)."),
        ],
        purpose: Annotated[
            CredentialPurpose,
            Field(description="Closed enum: role this credential plays."),
        ],
        secret_ref: Annotated[
            str,
            Field(
                min_length=1,
                description=(
                    "Opaque pointer to secret material in SecretStore. "
                    "Raw bytes NEVER cross this wire."
                ),
            ),
        ],
        public_material_ref: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional opaque pointer to the public counterpart.",
            ),
        ] = None,
        expires_at: Annotated[
            datetime | None,
            Field(
                default=None,
                description=(
                    "Optional contractual upper bound; when set must lie strictly after now."
                ),
            ),
        ] = None,
    ) -> RegisterCredentialOutput:
        handler = get_handler()
        credential_id = await handler(
            RegisterCredential(
                facility_code=facility_code,
                audience=audience,
                purpose=purpose,
                secret_ref=secret_ref,
                public_material_ref=public_material_ref,
                expires_at=expires_at,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterCredentialOutput(credential_id=credential_id)
