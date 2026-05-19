"""MCP tool for the `define_calibration` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.calibration.aggregates.calibration import CALIBRATION_DESCRIPTION_MAX_LENGTH
from cora.calibration.features.define_calibration.command import DefineCalibration
from cora.calibration.features.define_calibration.handler import IdempotentHandler
from cora.calibration.quantities import CalibrationQuantity
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class DefineCalibrationOutput(BaseModel):
    """Structured output of the `define_calibration` MCP tool."""

    calibration_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_calibration` tool on the given MCP server."""

    @mcp.tool(
        name="define_calibration",
        description=(
            "Define a new empirical instrument-value record (Calibration). "
            "Identity tuple is (subsystem_or_asset_id, quantity, "
            "operating_point); duplicates are rejected via Postgres jsonb "
            "UNIQUE on the projection. operating_point validates STRICT "
            "against the quantity's registered schema. Phase 12a-2."
        ),
    )
    async def define_calibration_tool(  # pyright: ignore[reportUnusedFunction]
        principal_id: Annotated[
            UUID,
            Field(description="Actor id authoring this calibration definition."),
        ],
        subsystem_or_asset_id: Annotated[
            UUID,
            Field(description="What this calibration is OF (Asset id)."),
        ],
        quantity: Annotated[
            CalibrationQuantity,
            Field(
                description=(
                    "The physical quantity being calibrated. Must be one "
                    "of the registered CalibrationQuantity values."
                ),
            ),
        ],
        operating_point: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Operating-regime dict; validated STRICT against the "
                    "quantity's operating_point_schema."
                ),
            ),
        ],
        description: Annotated[
            str | None,
            Field(
                default=None,
                max_length=CALIBRATION_DESCRIPTION_MAX_LENGTH,
                description=(
                    "Optional operator-prose notes (0-2000 chars). "
                    "Empty / whitespace-only is treated as absent."
                ),
            ),
        ] = None,
    ) -> DefineCalibrationOutput:
        handler = get_handler()
        calibration_id = await handler(
            DefineCalibration(
                subsystem_or_asset_id=subsystem_or_asset_id,
                quantity=quantity,
                operating_point=operating_point,
                description=description,
            ),
            principal_id=principal_id,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefineCalibrationOutput(calibration_id=calibration_id)
