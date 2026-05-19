"""MCP tool for the `list_practices` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.aggregates.practice import (
    PRACTICE_NAME_MAX_LENGTH,
    PRACTICE_VERSION_TAG_MAX_LENGTH,
)
from cora.recipe.features.list_practices.handler import Handler
from cora.recipe.features.list_practices.query import ListPractices, PracticeStatusFilter


class PracticeSummaryRow(BaseModel):
    practice_id: UUID
    name: str = Field(..., max_length=PRACTICE_NAME_MAX_LENGTH)
    method_id: UUID
    site_id: UUID
    status: PracticeStatusFilter
    version_tag: str | None = Field(default=None, max_length=PRACTICE_VERSION_TAG_MAX_LENGTH)
    created_at: datetime


class PracticeListOutput(BaseModel):
    """Structured output of the `list_practices` MCP tool."""

    items: list[PracticeSummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_practices` tool on the given MCP server."""

    @mcp.tool(
        name="list_practices",
        description=(
            "Cursor-paginated list of practices (facility-adapted "
            "method definitions). Optional `status` filter accepts: "
            "Defined, Versioned, Deprecated. Optional `method_id` "
            "filter narrows to Practices implementing one Method. "
            "Pass `cursor` from a previous page's `next_cursor` to "
            "fetch the next page."
        ),
    )
    async def list_practices_tool(  # pyright: ignore[reportUnusedFunction]
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        status: Annotated[
            PracticeStatusFilter | None,
            Field(description="Optional status filter; omit to list all."),
        ] = None,
        method_id: Annotated[
            UUID | None,
            Field(description="Optional Method-id filter."),
        ] = None,
    ) -> PracticeListOutput:
        handler = get_handler()
        page = await handler(
            ListPractices(cursor=cursor, limit=limit, status=status, method_id=method_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return PracticeListOutput(
            items=[
                PracticeSummaryRow(
                    practice_id=item.practice_id,
                    name=item.name,
                    method_id=item.method_id,
                    site_id=item.site_id,
                    status=item.status,  # type: ignore[arg-type]
                    version_tag=item.version_tag,
                    created_at=item.created_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
