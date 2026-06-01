"""MCP tool for the `list_permits` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.aggregates.permit import AbiTier, Direction, PermitStatus
from cora.federation.features.list_permits.handler import Handler
from cora.federation.features.list_permits.query import (
    ListPermits,
    PermitDirectionFilter,
    PermitStatusFilter,
)
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class PermitSummaryItemOutput(BaseModel):
    permit_id: UUID
    peer_facility_id: str = Field(..., min_length=1)
    direction: Direction
    allowed_credential_ids: list[UUID] = Field(default_factory=list[UUID])
    allowed_payload_types: list[str] = Field(default_factory=list[str])
    allowed_artifact_kinds: list[str] = Field(default_factory=list[str])
    abi_tier_floor: AbiTier
    expires_at: datetime
    defined_by_actor_id: UUID
    status: PermitStatus
    terms_kind: Direction
    defined_at: datetime
    activated_at: datetime | None = None
    suspended_at: datetime | None = None
    resumed_at: datetime | None = None
    revoked_at: datetime | None = None


class ListPermitsOutput(BaseModel):
    """Structured output of the `list_permits` MCP tool."""

    items: list[PermitSummaryItemOutput]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_permits` tool on the given MCP server."""

    @mcp.tool(
        name="list_permits",
        description=(
            "List federation Permits with cursor pagination + 3 optional "
            "filters: direction (Outbound / Inbound) / status (Defined / "
            "Active / Suspended / Revoked) / peer_facility_id. Returns "
            "sorted by defined_at ASC. Per-arc terms detail (scopes / "
            "read_scope / onward_action_scope / accepted_canonicalization_versions "
            "/ etc.) is NOT in the response; fetch get_permit for the full "
            "polymorphic terms VO."
        ),
    )
    async def list_permits_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None, Field(default=None, description="Opaque pagination cursor.")
        ] = None,
        limit: Annotated[
            int, Field(default=50, ge=1, le=100, description="Page size (1-100).")
        ] = 50,
        direction: Annotated[
            PermitDirectionFilter | None,
            Field(default=None, description="Direction filter (Outbound | Inbound)."),
        ] = None,
        status: Annotated[
            PermitStatusFilter | None,
            Field(default=None, description="Status filter."),
        ] = None,
        peer_facility_id: Annotated[
            str | None,
            Field(default=None, description="Peer-facility-id filter (opaque string)."),
        ] = None,
    ) -> ListPermitsOutput:
        handler = get_handler()
        page = await handler(
            ListPermits(
                cursor=cursor,
                limit=limit,
                direction=direction,
                status=status,
                peer_facility_id=peer_facility_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ListPermitsOutput(
            items=[
                PermitSummaryItemOutput(
                    permit_id=item.permit_id,
                    peer_facility_id=item.peer_facility_id,
                    direction=Direction(item.direction),
                    allowed_credential_ids=[UUID(str(c)) for c in item.allowed_credential_ids],
                    allowed_payload_types=[str(p) for p in item.allowed_payload_types],
                    allowed_artifact_kinds=[str(k) for k in item.allowed_artifact_kinds],
                    abi_tier_floor=AbiTier(item.abi_tier_floor),
                    expires_at=item.expires_at,
                    defined_by_actor_id=item.defined_by_actor_id,
                    status=PermitStatus(item.status),
                    terms_kind=Direction(item.terms_kind),
                    defined_at=item.defined_at,
                    activated_at=item.activated_at,
                    suspended_at=item.suspended_at,
                    resumed_at=item.resumed_at,
                    revoked_at=item.revoked_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
