"""MCP tool for the `get_calibration` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.calibration._calibration_dtos import (
    SourceAssertedDTO,
    SourceComputedDTO,
    SourceMeasuredDTO,
    dto_from_source,
)
from cora.calibration.aggregates.calibration import (
    Calibration,
    CalibrationRevision,
    CalibrationStatus,
)
from cora.calibration.features.get_calibration.handler import Handler
from cora.calibration.features.get_calibration.query import GetCalibration
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RevisionOutput(BaseModel):
    """MCP-tool structured output for one revision."""

    revision_id: UUID
    value: dict[str, Any]
    status: CalibrationStatus
    source: SourceMeasuredDTO | SourceComputedDTO | SourceAssertedDTO = Field(
        ..., discriminator="kind"
    )
    established_at: datetime
    established_by: UUID
    decided_by_decision_id: UUID | None = None
    supersedes_revision_id: UUID | None = None


class GetCalibrationOutput(BaseModel):
    """Structured output of the `get_calibration` MCP tool.

    `defined_at` is folded on the aggregate per the fold-symmetry rule;
    `last_revised_at` remains projection-sourced and nullable on the
    wire when the projection lags or the deps lack a pool (in-memory
    test mode). Mirrors the REST `CalibrationResponse` shape.
    """

    id: UUID
    target_id: UUID
    quantity: str
    operating_point: dict[str, Any]
    description: str | None
    revisions: list[RevisionOutput]
    defined_at: datetime
    last_revised_at: datetime | None = None
    defined_by: UUID


def _revision_output(revision: CalibrationRevision) -> RevisionOutput:
    return RevisionOutput(
        revision_id=revision.revision_id,
        value=revision.value,
        status=revision.status,
        source=dto_from_source(revision.source),
        established_at=revision.established_at,
        established_by=revision.established_by,
        decided_by_decision_id=revision.decided_by_decision_id,
        supersedes_revision_id=revision.supersedes_revision_id,
    )


def _output_from_view(
    calibration: Calibration,
    last_revised_at: datetime | None,
) -> GetCalibrationOutput:
    return GetCalibrationOutput(
        id=calibration.id,
        target_id=calibration.target_id,
        quantity=calibration.quantity,
        operating_point=calibration.operating_point,
        description=calibration.description,
        revisions=[_revision_output(r) for r in calibration.revisions],
        defined_at=calibration.defined_at,
        last_revised_at=last_revised_at,
        defined_by=calibration.defined_by,
    )


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_calibration` tool on the given MCP server."""

    @mcp.tool(
        name="get_calibration",
        description=(
            "Read the current state of an existing Calibration by id "
            "(identity tuple + description + every appended revision "
            "with source provenance + status). Returns null when no "
            "calibration matches."
        ),
    )
    async def get_calibration_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        calibration_id: Annotated[
            UUID,
            Field(description="Target calibration's id."),
        ],
    ) -> GetCalibrationOutput | None:
        handler = get_handler()
        view = await handler(
            GetCalibration(calibration_id=calibration_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if view is None:
            return None
        return _output_from_view(
            view.calibration,
            view.timestamps.last_revised_at if view.timestamps is not None else None,
        )
