"""MCP tool for the `append_run_reading` slice (Phase 6f-5b)."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.run.features.append_run_reading.command import (
    AppendRunReadings,
    RunReadingInput,
)
from cora.run.features.append_run_reading.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `append_run_reading` tool on the given MCP server.

    Single-entry shape for MCP simplicity (one tool call = one
    reading). HTTP route accepts batches; agents typically reason
    about one reading at a time and the per-call overhead is fine.
    """

    @mcp.tool(
        name="append_run_reading",
        description=(
            "Append one polymorphic sensor / motor reading to a Run's "
            "reading logbook. Lazy-opens the logbook on first call. "
            "`sampling_procedure` discriminates baseline (snapshot at "
            "run boundary) vs monitor (sub-Hz time-series). Rejects "
            "when Run is in a terminal status."
        ),
    )
    async def append_run_reading_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        run_id: Annotated[UUID, Field(description="Target run's id.")],
        channel_name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=255,
                description="Sensor or motor identifier.",
            ),
        ],
        value: Annotated[
            float,
            Field(allow_inf_nan=False, description="Scalar reading value."),
        ],
        sampled_at: Annotated[
            datetime,
            Field(description="When the sensor captured the value (SOSA phenomenonTime)."),
        ],
        sampling_procedure: Annotated[
            Literal["baseline", "monitor"],
            Field(
                description=(
                    "SOSA-aligned discriminator. 'baseline' = snapshot "
                    "at run boundary; 'monitor' = sub-Hz time-series "
                    "during the run (Bluesky monitor stream)."
                ),
            ),
        ],
        units: Annotated[
            str | None,
            Field(default=None, max_length=64, description="Optional unit string."),
        ] = None,
    ) -> int:
        handler = get_handler()
        entry = RunReadingInput(
            event_id=uuid4(),
            channel_name=channel_name,
            value=value,
            sampled_at=sampled_at,
            sampling_procedure=sampling_procedure,
            units=units,
        )
        return await handler(
            AppendRunReadings(run_id=run_id, entries=(entry,)),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
