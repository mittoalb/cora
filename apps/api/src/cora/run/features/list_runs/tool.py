"""MCP tool for the `list_runs` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.run._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.run.aggregates.run import RUN_NAME_MAX_LENGTH
from cora.run.features.list_runs.handler import Handler
from cora.run.features.list_runs.query import ListRuns, RunStatusFilter

_RAID_MAX_LENGTH = 2048


class RunSummaryRow(BaseModel):
    run_id: UUID
    name: str = Field(..., max_length=RUN_NAME_MAX_LENGTH)
    plan_id: UUID
    subject_id: UUID | None
    raid: str | None = Field(default=None, max_length=_RAID_MAX_LENGTH)
    status: RunStatusFilter
    created_at: datetime
    parameter_overrides_present: bool = Field(
        default=False,
        description=(
            "True iff the Run was started with operator-supplied "
            "parameter_overrides (Phase 6g-c). The full overrides + "
            "effective_parameters dicts are loaded on demand via `get_run`."
        ),
    )


class RunListOutput(BaseModel):
    """Structured output of the `list_runs` MCP tool."""

    items: list[RunSummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_runs` tool on the given MCP server."""

    @mcp.tool(
        name="list_runs",
        description=(
            "Cursor-paginated list of runs (Plan + optional Subject "
            "execution instances). Optional `status` filter accepts: "
            "Running, Held, Completed, Aborted, Stopped, Truncated. "
            "Optional `plan_id` filter narrows to Runs bound to one "
            "Plan. Pass `cursor` from a previous page's `next_cursor` "
            "to fetch the next page."
        ),
    )
    async def list_runs_tool(  # pyright: ignore[reportUnusedFunction]
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        status: Annotated[
            RunStatusFilter | None,
            Field(description="Optional status filter; omit to list all."),
        ] = None,
        plan_id: Annotated[
            UUID | None,
            Field(description="Optional Plan-id filter."),
        ] = None,
    ) -> RunListOutput:
        handler = get_handler()
        page = await handler(
            ListRuns(cursor=cursor, limit=limit, status=status, plan_id=plan_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return RunListOutput(
            items=[
                RunSummaryRow(
                    run_id=item.run_id,
                    name=item.name,
                    plan_id=item.plan_id,
                    subject_id=item.subject_id,
                    raid=item.raid,
                    status=item.status,  # type: ignore[arg-type]
                    created_at=item.created_at,
                    parameter_overrides_present=item.parameter_overrides_present,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
