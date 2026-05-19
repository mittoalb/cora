"""MCP tool for the `get_calibration` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
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
from cora.infrastructure.observability import current_correlation_id


class RevisionOutput(BaseModel):
    """MCP-tool structured output for one revision."""

    revision_id: UUID
    value: dict[str, Any]
    status: CalibrationStatus
    source: SourceMeasuredDTO | SourceComputedDTO | SourceAssertedDTO = Field(
        ..., discriminator="kind"
    )
    established_at: datetime
    established_by_actor_id: UUID
    decided_by_decision_id: UUID | None = None
    supersedes_revision_id: UUID | None = None


class GetCalibrationOutput(BaseModel):
    """Structured output of the `get_calibration` MCP tool."""

    id: UUID
    subsystem_or_asset_id: UUID
    quantity: str
    operating_point: dict[str, Any]
    description: str | None
    revisions: list[RevisionOutput]
    defined_at: datetime
    last_revised_at: datetime
    defined_by_actor_id: UUID


def _revision_output(revision: CalibrationRevision) -> RevisionOutput:
    return RevisionOutput(
        revision_id=revision.revision_id,
        value=revision.value,
        status=revision.status,
        source=dto_from_source(revision.source),
        established_at=revision.established_at,
        established_by_actor_id=revision.established_by_actor_id,
        decided_by_decision_id=revision.decided_by_decision_id,
        supersedes_revision_id=revision.supersedes_revision_id,
    )


def _output_from_state(calibration: Calibration) -> GetCalibrationOutput:
    return GetCalibrationOutput(
        id=calibration.id,
        subsystem_or_asset_id=calibration.subsystem_or_asset_id,
        quantity=calibration.quantity,
        operating_point=calibration.operating_point,
        description=calibration.description,
        revisions=[_revision_output(r) for r in calibration.revisions],
        defined_at=calibration.defined_at,
        last_revised_at=calibration.last_revised_at,
        defined_by_actor_id=calibration.defined_by_actor_id,
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
        principal_id: Annotated[
            UUID,
            Field(description="Actor id reading the calibration."),
        ],
        calibration_id: Annotated[
            UUID,
            Field(description="Target calibration's id."),
        ],
    ) -> GetCalibrationOutput | None:
        handler = get_handler()
        calibration = await handler(
            GetCalibration(calibration_id=calibration_id),
            principal_id=principal_id,
            correlation_id=current_correlation_id(),
        )
        return _output_from_state(calibration) if calibration is not None else None
