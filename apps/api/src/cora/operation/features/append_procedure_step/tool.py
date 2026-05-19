"""MCP tool for the `append_procedure_step` slice (Phase 10c-b iter 2).

The MCP tool exposes the SAME contract as the HTTP route: a batch of
polymorphic step entries, lazy open-on-first-write, dedup via Postgres
PK on event_id.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.operation.aggregates.procedure import StepKind
from cora.operation.features.append_procedure_step.command import (
    AppendProcedureSteps,
    ProcedureStepInput,
)
from cora.operation.features.append_procedure_step.handler import Handler


class _ProcedureStepEntry(BaseModel):
    """One step entry's input payload (mirrors HTTP route shape).

    `step_kind` reuses the `StepKind` Literal from the aggregate to
    keep the wire contract single-sourced (matches route.py posture).
    """

    event_id: UUID
    step_kind: StepKind
    payload: dict[str, Any]
    sampled_at: datetime
    occurred_at: datetime | None = None

    model_config = {"extra": "forbid"}


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `append_procedure_step` tool on the given MCP server."""

    @mcp.tool(
        name="append_procedure_step",
        description=(
            "Append a batch of polymorphic procedural steps "
            "(setpoint / action / check) to a Procedure's steps "
            "logbook. Requires the Procedure to currently be in "
            "`Running`. Lazy open-on-first-write: the steps logbook "
            "attaches to the Procedure on the first append. Dedup "
            "via UUIDv7 event_id."
        ),
    )
    async def append_procedure_step_tool(  # pyright: ignore[reportUnusedFunction]
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
        entries: Annotated[
            list[_ProcedureStepEntry],
            Field(
                min_length=1,
                max_length=500,
                description="Batch of step entries to append (1-500).",
            ),
        ],
    ) -> int:
        handler = get_handler()
        return await handler(
            AppendProcedureSteps(
                procedure_id=procedure_id,
                entries=tuple(
                    ProcedureStepInput(
                        event_id=e.event_id,
                        step_kind=e.step_kind,
                        payload=e.payload,
                        sampled_at=e.sampled_at,
                        occurred_at=e.occurred_at,
                    )
                    for e in entries
                ),
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
