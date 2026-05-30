"""MCP tool for the `list_credentials` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.aggregates.credential import CredentialPurpose, CredentialStatus
from cora.federation.features.list_credentials.handler import Handler
from cora.federation.features.list_credentials.query import (
    CredentialPurposeFilter,
    CredentialStatusFilter,
    ListCredentials,
)
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class CredentialSummaryItemOutput(BaseModel):
    credential_id: UUID
    facility_id: str
    audience: str
    purpose: CredentialPurpose
    expires_at: datetime | None = None
    status: CredentialStatus
    registered_at: datetime
    rotation_started_at: datetime | None = None
    revoked_at: datetime | None = None


class ListCredentialsOutput(BaseModel):
    """Structured output of the `list_credentials` MCP tool."""

    items: list[CredentialSummaryItemOutput]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_credentials` tool on the given MCP server."""

    @mcp.tool(
        name="list_credentials",
        description=(
            "List credentials with cursor pagination + 3 optional filters: "
            "facility_id / purpose / status. Returns sorted by "
            "registered_at ASC. Opaque secret-material refs (secret_ref, "
            "public_material_ref, rotation_pending_*_ref) are NOT in the "
            "response; fetch get_credential for those."
        ),
    )
    async def list_credentials_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None, Field(default=None, description="Opaque pagination cursor.")
        ] = None,
        limit: Annotated[
            int, Field(default=50, ge=1, le=100, description="Page size (1-100).")
        ] = 50,
        facility_id: Annotated[
            str | None, Field(default=None, description="Facility filter.")
        ] = None,
        purpose: Annotated[
            CredentialPurposeFilter | None,
            Field(default=None, description="Purpose filter."),
        ] = None,
        status: Annotated[
            CredentialStatusFilter | None,
            Field(default=None, description="Status filter."),
        ] = None,
    ) -> ListCredentialsOutput:
        handler = get_handler()
        page = await handler(
            ListCredentials(
                cursor=cursor,
                limit=limit,
                facility_id=facility_id,
                purpose=purpose,
                status=status,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ListCredentialsOutput(
            items=[
                CredentialSummaryItemOutput(
                    credential_id=item.credential_id,
                    facility_id=item.facility_id,
                    audience=item.audience,
                    purpose=CredentialPurpose(item.purpose),
                    expires_at=item.expires_at,
                    status=CredentialStatus(item.status),
                    registered_at=item.registered_at,
                    rotation_started_at=item.rotation_started_at,
                    revoked_at=item.revoked_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
