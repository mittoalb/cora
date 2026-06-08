"""MCP tool for the `get_credential` query slice.

Per AH#6 of the locked design, the output surfaces `secret_ref`,
`public_material_ref`, `rotation_pending_secret_ref`, and
`rotation_pending_public_material_ref` as OPAQUE STRINGS only; raw
secret bytes never cross this wire (the aggregate never holds them).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.aggregates.credential import (
    Credential,
    CredentialPurpose,
    CredentialStatus,
)
from cora.federation.features.get_credential.handler import Handler
from cora.federation.features.get_credential.query import GetCredential
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class GetCredentialOutput(BaseModel):
    """Structured output of the `get_credential` MCP tool.

    `registered_at` and `registered_by` are sourced from aggregate
    state (folded from the genesis envelope per the fold-symmetry
    Path C reversal); `rotation_started_at` is projection-sourced
    and nullable when the projection lags or the deps lack a pool
    (in-memory test mode). Mirrors the REST `CredentialResponse`
    shape.
    """

    id: UUID
    facility_code: str
    audience: str
    purpose: CredentialPurpose
    secret_ref: str
    public_material_ref: str | None
    expires_at: datetime | None
    registered_by: UUID
    registered_at: datetime
    rotation_pending_secret_ref: str | None
    rotation_pending_public_material_ref: str | None
    status: CredentialStatus
    rotation_started_at: datetime | None = None


def _output_from_view(
    credential: Credential,
    rotation_started_at: datetime | None,
) -> GetCredentialOutput:
    return GetCredentialOutput(
        id=credential.id,
        facility_code=credential.facility_code.value,
        audience=credential.audience,
        purpose=credential.purpose,
        secret_ref=credential.secret_ref,
        public_material_ref=credential.public_material_ref,
        expires_at=credential.expires_at,
        registered_by=credential.registered_by,
        registered_at=credential.registered_at,
        rotation_pending_secret_ref=credential.rotation_pending_secret_ref,
        rotation_pending_public_material_ref=credential.rotation_pending_public_material_ref,
        status=credential.status,
        rotation_started_at=rotation_started_at,
    )


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_credential` tool on the given MCP server."""

    @mcp.tool(
        name="get_credential",
        description=(
            "Read the current state of an existing federation Credential "
            "by id (identity + purpose + opaque pointers + status + "
            "rotation-pending pointers + lifecycle timestamps). Returns "
            "null when no credential matches. `secret_ref` and the other "
            "pointer fields are opaque strings; raw secret bytes never "
            "cross this wire."
        ),
    )
    async def get_credential_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        credential_id: Annotated[
            UUID,
            Field(description="Target credential's id."),
        ],
    ) -> GetCredentialOutput | None:
        handler = get_handler()
        view = await handler(
            GetCredential(credential_id=credential_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if view is None:
            return None
        return _output_from_view(
            view.credential,
            view.timestamps.rotation_started_at if view.timestamps is not None else None,
        )
