"""MCP tool for the `list_supplies` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.supply._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.supply.aggregates.supply import (
    SUPPLY_KIND_MAX_LENGTH,
    SUPPLY_NAME_MAX_LENGTH,
    SUPPLY_REASON_MAX_LENGTH,
    SupplyScope,
    SupplyStatus,
    TriggerSource,
)
from cora.supply.features.list_supplies.handler import Handler
from cora.supply.features.list_supplies.query import (
    ListSupplies,
    SupplyScopeFilter,
    SupplyStatusFilter,
)


class SupplySummaryRow(BaseModel):
    supply_id: UUID
    scope: SupplyScope
    kind: str = Field(..., max_length=SUPPLY_KIND_MAX_LENGTH)
    name: str = Field(..., max_length=SUPPLY_NAME_MAX_LENGTH)
    status: SupplyStatus
    registered_at: datetime
    last_status_changed_at: datetime | None = None
    last_status_reason: str | None = Field(default=None, max_length=SUPPLY_REASON_MAX_LENGTH)
    last_trigger: TriggerSource | None = None


class SupplyListOutput(BaseModel):
    """Structured output of the `list_supplies` MCP tool."""

    items: list[SupplySummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_supplies` tool on the given MCP server."""

    @mcp.tool(
        name="list_supplies",
        description=(
            "Cursor-paginated list of supplies. Optional filters: "
            "`scope` (Facility / Sector / Beamline), `kind` (free-form "
            "exact match, e.g. 'LiquidNitrogen'), `status` (Unknown / "
            "Available / Degraded / Unavailable / Recovering). Pass "
            "`cursor` from a previous page's `next_cursor` to fetch "
            "the next page."
        ),
    )
    async def list_supplies_tool(  # pyright: ignore[reportUnusedFunction]
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        scope: Annotated[
            SupplyScopeFilter | None,
            Field(description="Optional scope filter; omit to list all."),
        ] = None,
        kind: Annotated[
            str | None,
            Field(
                min_length=1,
                max_length=SUPPLY_KIND_MAX_LENGTH,
                description="Optional kind filter (exact match); omit to list all.",
            ),
        ] = None,
        status: Annotated[
            SupplyStatusFilter | None,
            Field(description="Optional status filter; omit to list all."),
        ] = None,
    ) -> SupplyListOutput:
        handler = get_handler()
        page = await handler(
            ListSupplies(cursor=cursor, limit=limit, scope=scope, kind=kind, status=status),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return SupplyListOutput(
            items=[
                SupplySummaryRow(
                    supply_id=item.supply_id,
                    scope=SupplyScope(item.scope),
                    kind=item.kind,
                    name=item.name,
                    status=SupplyStatus(item.status),
                    registered_at=item.registered_at,
                    last_status_changed_at=item.last_status_changed_at,
                    last_status_reason=item.last_status_reason,
                    last_trigger=(
                        TriggerSource(item.last_trigger) if item.last_trigger is not None else None
                    ),
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
