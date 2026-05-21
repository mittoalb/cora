"""MCP tool for the `list_zones` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.aggregates.zone import ZONE_NAME_MAX_LENGTH
from cora.trust.features.list_zones.handler import Handler
from cora.trust.features.list_zones.query import ListZones


class ZoneSummaryRow(BaseModel):
    zone_id: UUID
    name: str = Field(..., max_length=ZONE_NAME_MAX_LENGTH)
    created_at: datetime


class ZoneListOutput(BaseModel):
    """Structured output of the `list_zones` MCP tool."""

    items: list[ZoneSummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_zones` tool on the given MCP server."""

    @mcp.tool(
        name="list_zones",
        description=(
            "Cursor-paginated list of Trust zones. Pass `cursor` from "
            "a previous page's `next_cursor` to fetch the next page."
        ),
    )
    async def list_zones_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
    ) -> ZoneListOutput:
        handler = get_handler()
        page = await handler(
            ListZones(cursor=cursor, limit=limit),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ZoneListOutput(
            items=[
                ZoneSummaryRow(
                    zone_id=item.zone_id,
                    name=item.name,
                    created_at=item.created_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
