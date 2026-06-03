"""MCP tool for the `append_calibration_revision` slice.

Agent subscribers (for example, a future `RotationCenterRefiner`) are the
primary intended callers. The tool surface mirrors the REST route's
field shape exactly.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.calibration._calibration_dtos import SourceDTO, source_from_dto
from cora.calibration.aggregates.calibration import CalibrationStatus
from cora.calibration.features.append_calibration_revision.command import (
    AppendCalibrationRevision,
)
from cora.calibration.features.append_calibration_revision.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class AppendCalibrationRevisionOutput(BaseModel):
    """Structured output of the `append_calibration_revision` MCP tool."""

    revision_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `append_calibration_revision` tool on the given MCP server."""

    @mcp.tool(
        name="append_calibration_revision",
        description=(
            "Append a new revision to an existing Calibration. Validates "
            "value STRICT against the quantity's value_schema; verifies "
            "supersedes_revision_id (when provided) exists on the same "
            "aggregate. Source is a tagged union: Measured / Computed / "
            "Asserted. Idempotency-Key wrapping recommended for agent "
            "subscribers."
        ),
    )
    async def append_calibration_revision_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        calibration_id: Annotated[
            UUID,
            Field(description="Target calibration's id."),
        ],
        value: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Revision value dict; validated STRICT against the "
                    "calibration's quantity-specific VALUE_SCHEMA."
                ),
            ),
        ],
        status: Annotated[
            CalibrationStatus,
            Field(
                description=("Confidence tier of this revision: Provisional or Verified."),
            ),
        ],
        source: Annotated[
            SourceDTO,
            Field(
                description=(
                    "Tagged source provenance: {kind: 'Measured', "
                    "procedure_id} / {kind: 'Computed', dataset_id} / "
                    "{kind: 'Asserted', actor_id}."
                ),
            ),
        ],
        decided_by_decision_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Optional Decision id justifying this revision. Maps "
                    "to prov:wasInformedBy. Not verified at write path."
                ),
            ),
        ] = None,
        supersedes_revision_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Optional prior revision id (same aggregate) this "
                    "revision supersedes. Cross-aggregate supersession "
                    "is forbidden."
                ),
            ),
        ] = None,
    ) -> AppendCalibrationRevisionOutput:
        handler = get_handler()
        revision_id = await handler(
            AppendCalibrationRevision(
                calibration_id=calibration_id,
                value=value,
                status=status,
                source=source_from_dto(source),
                decided_by_decision_id=decided_by_decision_id,
                supersedes_revision_id=supersedes_revision_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return AppendCalibrationRevisionOutput(revision_id=revision_id)
