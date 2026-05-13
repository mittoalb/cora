"""MCP tool for the `list_conduits` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.trust._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.trust.aggregates.conduit import CONDUIT_NAME_MAX_LENGTH
from cora.trust.features.list_conduits.handler import Handler
from cora.trust.features.list_conduits.query import ListConduits


class ConduitSummaryRow(BaseModel):
    conduit_id: UUID
    name: str = Field(..., max_length=CONDUIT_NAME_MAX_LENGTH)
    source_zone_id: UUID
    target_zone_id: UUID
    created_at: datetime


class ConduitListOutput(BaseModel):
    """Structured output of the `list_conduits` MCP tool."""

    items: list[ConduitSummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_conduits` tool on the given MCP server."""

    @mcp.tool(
        name="list_conduits",
        description=(
            "Cursor-paginated list of Trust conduits (governed comms "
            "paths between two Zones). Optional `source_zone_id` / "
            "`target_zone_id` filters narrow by endpoint. Pass "
            "`cursor` from a previous page's `next_cursor` to fetch "
            "the next page."
        ),
    )
    async def list_conduits_tool(  # pyright: ignore[reportUnusedFunction]
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        source_zone_id: Annotated[
            UUID | None,
            Field(description="Optional source-zone filter; omit for any source."),
        ] = None,
        target_zone_id: Annotated[
            UUID | None,
            Field(description="Optional target-zone filter; omit for any target."),
        ] = None,
    ) -> ConduitListOutput:
        handler = get_handler()
        page = await handler(
            ListConduits(
                cursor=cursor,
                limit=limit,
                source_zone_id=source_zone_id,
                target_zone_id=target_zone_id,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return ConduitListOutput(
            items=[
                ConduitSummaryRow(
                    conduit_id=item.conduit_id,
                    name=item.name,
                    source_zone_id=item.source_zone_id,
                    target_zone_id=item.target_zone_id,
                    created_at=item.created_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
