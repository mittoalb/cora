"""MCP tool for the `list_seals` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.aggregates.seal.state import SealStatus
from cora.federation.features.list_seals.handler import Handler
from cora.federation.features.list_seals.query import ListSeals, SealStatusFilter
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class SealSummaryItemOutput(BaseModel):
    facility_id: str
    online_credential_id: UUID
    offline_credential_id: UUID
    current_head_hash: str | None = None
    current_sequence_number: int
    initialized_by: UUID
    last_signed_by: UUID | None = None
    status: SealStatus
    initialized_at: datetime
    last_signed_at: datetime | None = None


class ListSealsOutput(BaseModel):
    """Structured output of the `list_seals` MCP tool."""

    items: list[SealSummaryItemOutput]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_seals` tool on the given MCP server."""

    @mcp.tool(
        name="list_seals",
        description=(
            "List Seal singletons (one per facility) with cursor pagination "
            "+ optional status filter (Live / Republishing). Returns sorted "
            "by initialized_at ASC."
        ),
    )
    async def list_seals_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None, Field(default=None, description="Opaque pagination cursor.")
        ] = None,
        limit: Annotated[
            int, Field(default=50, ge=1, le=100, description="Page size (1-100).")
        ] = 50,
        status: Annotated[
            SealStatusFilter | None,
            Field(default=None, description="Status filter (Live or Republishing)."),
        ] = None,
    ) -> ListSealsOutput:
        handler = get_handler()
        page = await handler(
            ListSeals(cursor=cursor, limit=limit, status=status),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ListSealsOutput(
            items=[
                SealSummaryItemOutput(
                    facility_id=item.facility_id,
                    online_credential_id=item.online_credential_id,
                    offline_credential_id=item.offline_credential_id,
                    current_head_hash=item.current_head_hash,
                    current_sequence_number=item.current_sequence_number,
                    initialized_by=item.initialized_by,
                    last_signed_by=item.last_signed_by,
                    status=SealStatus(item.status),
                    initialized_at=item.initialized_at,
                    last_signed_at=item.last_signed_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
