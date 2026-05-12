"""MCP tool for the `list_plans` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.aggregates.plan import (
    PLAN_NAME_MAX_LENGTH,
    PLAN_VERSION_TAG_MAX_LENGTH,
)
from cora.recipe.features.list_plans.handler import Handler
from cora.recipe.features.list_plans.query import ListPlans, PlanStatusFilter


class PlanSummaryRow(BaseModel):
    plan_id: UUID
    name: str = Field(..., max_length=PLAN_NAME_MAX_LENGTH)
    practice_id: UUID
    method_id: UUID
    status: PlanStatusFilter
    version_tag: str | None = Field(default=None, max_length=PLAN_VERSION_TAG_MAX_LENGTH)
    created_at: datetime


class PlanListOutput(BaseModel):
    """Structured output of the `list_plans` MCP tool."""

    items: list[PlanSummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_plans` tool on the given MCP server."""

    @mcp.tool(
        name="list_plans",
        description=(
            "Cursor-paginated list of plans (Practice + multi-asset "
            "binding ready for execution). Optional `status` filter "
            "accepts: Defined, Versioned, Deprecated. Optional "
            "`practice_id` filter narrows to Plans binding one "
            "Practice. Pass `cursor` from a previous page's "
            "`next_cursor` to fetch the next page."
        ),
    )
    async def list_plans_tool(  # pyright: ignore[reportUnusedFunction]
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        status: Annotated[
            PlanStatusFilter | None,
            Field(description="Optional status filter; omit to list all."),
        ] = None,
        practice_id: Annotated[
            UUID | None,
            Field(description="Optional Practice-id filter."),
        ] = None,
    ) -> PlanListOutput:
        handler = get_handler()
        page = await handler(
            ListPlans(cursor=cursor, limit=limit, status=status, practice_id=practice_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return PlanListOutput(
            items=[
                PlanSummaryRow(
                    plan_id=item.plan_id,
                    name=item.name,
                    practice_id=item.practice_id,
                    method_id=item.method_id,
                    status=item.status,  # type: ignore[arg-type]
                    version_tag=item.version_tag,
                    created_at=item.created_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
