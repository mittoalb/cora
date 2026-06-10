"""MCP tool for the `list_clearance_templates` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.safety.aggregates.clearance_template import (
    CLEARANCE_TEMPLATE_CODE_MAX_LENGTH,
    CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH,
)
from cora.safety.features.list_clearance_templates.handler import Handler
from cora.safety.features.list_clearance_templates.query import (
    ClearanceTemplateStatusFilter,
    ListClearanceTemplates,
)


class ClearanceTemplateSummaryRow(BaseModel):
    template_id: UUID
    code: str = Field(..., max_length=CLEARANCE_TEMPLATE_CODE_MAX_LENGTH)
    title: str = Field(..., max_length=CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH)
    facility_code: str
    version: int
    status: ClearanceTemplateStatusFilter
    defined_at: datetime


class ClearanceTemplateListOutput(BaseModel):
    """Structured output of the `list_clearance_templates` MCP tool."""

    items: list[ClearanceTemplateSummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_clearance_templates` tool on the given MCP server."""

    @mcp.tool(
        name="list_clearance_templates",
        description=(
            "Cursor-paginated list of clearance templates. Optional filters: "
            "`facility_code` (exact match), `status` (one of: Draft, Active, "
            "Deprecated, Withdrawn), `code` (exact match). Pass `cursor` from "
            "a previous page's `next_cursor` to fetch the next page."
        ),
    )
    async def list_clearance_templates_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        facility_code: Annotated[
            str | None,
            Field(description="Optional facility-code filter; omit to list all."),
        ] = None,
        status: Annotated[
            ClearanceTemplateStatusFilter | None,
            Field(description="Optional status filter; omit to list all."),
        ] = None,
        code: Annotated[
            str | None,
            Field(description="Optional code filter; omit to list all."),
        ] = None,
    ) -> ClearanceTemplateListOutput:
        handler = get_handler()
        page = await handler(
            ListClearanceTemplates(
                cursor=cursor,
                limit=limit,
                facility_code=facility_code,
                status=status,
                code=code,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ClearanceTemplateListOutput(
            items=[
                ClearanceTemplateSummaryRow(
                    template_id=item.template_id,
                    code=item.code,
                    title=item.title,
                    facility_code=item.facility_code,
                    version=item.version,
                    status=item.status,
                    defined_at=item.defined_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
