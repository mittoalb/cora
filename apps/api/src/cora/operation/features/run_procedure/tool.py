"""MCP tool for the `run_procedure` slice.

Mirrors the REST route: accepts a discriminated step list, returns
a structured RunProcedureResult summary. Failures land in the
return value (not raised); the LLM caller inspects `succeeded` +
`failure` to decide retry / abort / escalation.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation.features.run_procedure.command import RunProcedure
from cora.operation.features.run_procedure.handler import Handler
from cora.operation.features.run_procedure.route import (
    RunProcedureRequest,
    RunProcedureResponse,
    result_to_wire,
    step_from_wire,
)


class _ToolResult(BaseModel):
    """MCP-shape mirror of `RunProcedureResponse` for tool-output validation."""

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    failure: dict[str, Any] | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `run_procedure` tool on the given MCP server."""

    @mcp.tool(
        name="run_procedure",
        description=(
            "Conduct an existing Procedure end-to-end: start it, walk the "
            "supplied step list via the ControlPort (setpoint writes), "
            "the action registry (named action invocations), and read-back "
            "checks (EqualsCriterion or WithinToleranceCriterion criteria); then complete on "
            "success or abort on the first step failure. Returns a structured "
            "summary; failures DO NOT raise."
        ),
    )
    async def run_procedure_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
        body: Annotated[
            RunProcedureRequest,
            Field(description="Step list the Conductor walks in order."),
        ],
    ) -> _ToolResult:
        handler = get_handler()
        command = RunProcedure(
            procedure_id=procedure_id,
            steps=tuple(step_from_wire(s) for s in body.steps),
        )
        result = await handler(
            command,
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        wire: RunProcedureResponse = result_to_wire(result)
        return _ToolResult(
            procedure_id=wire.procedure_id,
            completed_count=wire.completed_count,
            succeeded=wire.succeeded,
            failure=wire.failure.model_dump() if wire.failure is not None else None,
        )
