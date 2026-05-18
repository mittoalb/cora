"""MCP tool for the `list_families` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.aggregates.family import (
    FAMILY_NAME_MAX_LENGTH,
    FAMILY_VERSION_TAG_MAX_LENGTH,
)
from cora.equipment.features.list_families.handler import Handler
from cora.equipment.features.list_families.query import (
    FamilyStatusFilter,
    ListFamilies,
)
from cora.infrastructure.observability import current_correlation_id


class FamilySummaryRow(BaseModel):
    family_id: UUID
    name: str = Field(..., max_length=FAMILY_NAME_MAX_LENGTH)
    status: FamilyStatusFilter
    version_tag: str | None = Field(default=None, max_length=FAMILY_VERSION_TAG_MAX_LENGTH)
    created_at: datetime


class FamilyListOutput(BaseModel):
    """Structured output of the `list_families` MCP tool."""

    items: list[FamilySummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_families` tool on the given MCP server."""

    @mcp.tool(
        name="list_families",
        description=(
            "Cursor-paginated list of families. Optional `status` "
            "filter accepts: Defined, Versioned, Deprecated. Pass "
            "`cursor` from a previous page's `next_cursor` to fetch "
            "the next page."
        ),
    )
    async def list_families_tool(  # pyright: ignore[reportUnusedFunction]
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        status: Annotated[
            FamilyStatusFilter | None,
            Field(description="Optional status filter; omit to list all."),
        ] = None,
    ) -> FamilyListOutput:
        handler = get_handler()
        page = await handler(
            ListFamilies(cursor=cursor, limit=limit, status=status),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return FamilyListOutput(
            items=[
                FamilySummaryRow(
                    family_id=item.family_id,
                    name=item.name,
                    status=item.status,  # type: ignore[arg-type]
                    version_tag=item.version_tag,
                    created_at=item.created_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
