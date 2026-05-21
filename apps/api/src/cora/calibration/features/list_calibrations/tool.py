"""MCP tool for the `list_calibrations` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.calibration.features.list_calibrations.handler import Handler
from cora.calibration.features.list_calibrations.query import (
    CalibrationSourceKindFilter,
    CalibrationStatusFilter,
    ListCalibrations,
)
from cora.calibration.quantities import CalibrationQuantity
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class CalibrationSummaryOutput(BaseModel):
    """One calibration row in the MCP tool's paginated output."""

    calibration_id: UUID
    subsystem_or_asset_id: UUID
    quantity: str
    operating_point: dict[str, Any]
    description: str | None = None
    defined_at: datetime
    last_revised_at: datetime
    defined_by_actor_id: UUID
    revision_count: int = Field(..., ge=0)
    latest_revision_status: str | None = None
    latest_revision_source_kind: str | None = None


class ListCalibrationsOutput(BaseModel):
    """Structured output of the `list_calibrations` MCP tool."""

    items: list[CalibrationSummaryOutput]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_calibrations` tool on the given MCP server."""

    @mcp.tool(
        name="list_calibrations",
        description=(
            "List Calibrations with cursor pagination + scope / quantity / "
            "latest-revision-status / latest-revision-source-kind filters. "
            "Empty calibrations (no revisions yet) carry null for the "
            "latest_* columns."
        ),
    )
    async def list_calibrations_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        cursor: Annotated[
            str | None,
            Field(default=None, description="Opaque cursor from a prior page."),
        ] = None,
        limit: Annotated[
            int,
            Field(default=50, ge=1, le=100, description="Page size; capped at 100."),
        ] = 50,
        subsystem_or_asset_id: Annotated[
            UUID | None,
            Field(default=None, description="Optional scope filter."),
        ] = None,
        quantity: Annotated[
            CalibrationQuantity | None,
            Field(default=None, description="Optional quantity filter."),
        ] = None,
        latest_revision_statuses: Annotated[
            list[CalibrationStatusFilter] | None,
            Field(
                default=None,
                description="Optional filter on latest-revision status (multi-value).",
            ),
        ] = None,
        latest_revision_source_kinds: Annotated[
            list[CalibrationSourceKindFilter] | None,
            Field(
                default=None,
                description=(
                    "Optional filter on latest-revision source kind "
                    "(measured / computed / asserted; multi-value)."
                ),
            ),
        ] = None,
    ) -> ListCalibrationsOutput:
        handler = get_handler()
        page = await handler(
            ListCalibrations(
                cursor=cursor,
                limit=limit,
                subsystem_or_asset_id=subsystem_or_asset_id,
                quantity=quantity.value if quantity is not None else None,
                latest_revision_statuses=latest_revision_statuses,
                latest_revision_source_kinds=latest_revision_source_kinds,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ListCalibrationsOutput(
            items=[
                CalibrationSummaryOutput(
                    calibration_id=item.calibration_id,
                    subsystem_or_asset_id=item.subsystem_or_asset_id,
                    quantity=item.quantity,
                    operating_point=item.operating_point,
                    description=item.description,
                    defined_at=item.defined_at,
                    last_revised_at=item.last_revised_at,
                    defined_by_actor_id=item.defined_by_actor_id,
                    revision_count=item.revision_count,
                    latest_revision_status=item.latest_revision_status,
                    latest_revision_source_kind=item.latest_revision_source_kind,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
