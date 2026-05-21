"""MCP tool for the `list_subjects` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.subject.aggregates.subject import SUBJECT_NAME_MAX_LENGTH
from cora.subject.features.list_subjects.handler import Handler
from cora.subject.features.list_subjects.query import ListSubjects, SubjectStatusFilter


class SubjectSummaryRow(BaseModel):
    subject_id: UUID
    name: str = Field(..., max_length=SUBJECT_NAME_MAX_LENGTH)
    status: SubjectStatusFilter
    created_at: datetime


class SubjectListOutput(BaseModel):
    """Structured output of the `list_subjects` MCP tool."""

    items: list[SubjectSummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_subjects` tool on the given MCP server."""

    @mcp.tool(
        name="list_subjects",
        description=(
            "Cursor-paginated list of subjects. Pass `cursor` from a "
            "previous page's `next_cursor` to fetch the next page. "
            "Optional `status` filter accepts: Received, Mounted, "
            "Measured, Removed, Returned, Stored, Discarded."
        ),
    )
    async def list_subjects_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        status: Annotated[
            SubjectStatusFilter | None,
            Field(description="Optional status filter; omit to list all."),
        ] = None,
    ) -> SubjectListOutput:
        handler = get_handler()
        page = await handler(
            ListSubjects(cursor=cursor, limit=limit, status=status),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return SubjectListOutput(
            items=[
                SubjectSummaryRow(
                    subject_id=item.subject_id,
                    name=item.name,
                    status=item.status,
                    created_at=item.created_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
