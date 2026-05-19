"""MCP tool for the `list_methods` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.aggregates.method import (
    METHOD_NAME_MAX_LENGTH,
    METHOD_VERSION_TAG_MAX_LENGTH,
)
from cora.recipe.features.list_methods.handler import Handler
from cora.recipe.features.list_methods.query import ListMethods, MethodStatusFilter


class MethodSummaryRow(BaseModel):
    method_id: UUID
    name: str = Field(..., max_length=METHOD_NAME_MAX_LENGTH)
    status: MethodStatusFilter
    version_tag: str | None = Field(default=None, max_length=METHOD_VERSION_TAG_MAX_LENGTH)
    created_at: datetime
    parameters_schema_present: bool = Field(
        default=False,
        description=(
            "True iff the Method has a parameters_schema declared (Phase "
            "6g-a). The schema content itself is loaded on demand via "
            "`get_method`."
        ),
    )


class MethodListOutput(BaseModel):
    """Structured output of the `list_methods` MCP tool."""

    items: list[MethodSummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_methods` tool on the given MCP server."""

    @mcp.tool(
        name="list_methods",
        description=(
            "Cursor-paginated list of methods (technique-class "
            "definitions). Optional `status` filter accepts: Defined, "
            "Versioned, Deprecated. Pass `cursor` from a previous "
            "page's `next_cursor` to fetch the next page."
        ),
    )
    async def list_methods_tool(  # pyright: ignore[reportUnusedFunction]
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        status: Annotated[
            MethodStatusFilter | None,
            Field(description="Optional status filter; omit to list all."),
        ] = None,
    ) -> MethodListOutput:
        handler = get_handler()
        page = await handler(
            ListMethods(cursor=cursor, limit=limit, status=status),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return MethodListOutput(
            items=[
                MethodSummaryRow(
                    method_id=item.method_id,
                    name=item.name,
                    status=item.status,  # type: ignore[arg-type]
                    version_tag=item.version_tag,
                    created_at=item.created_at,
                    parameters_schema_present=item.parameters_schema_present,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
