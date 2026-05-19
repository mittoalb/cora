"""MCP tool for the `register_procedure` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. MCP tools currently bypass header extraction
and use `SYSTEM_PRINCIPAL_ID` directly until the MCP auth-flow
phase lands.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.operation._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.operation.aggregates.procedure import (
    PROCEDURE_KIND_MAX_LENGTH,
    PROCEDURE_NAME_MAX_LENGTH,
)
from cora.operation.features.register_procedure.command import RegisterProcedure
from cora.operation.features.register_procedure.handler import IdempotentHandler


class RegisterProcedureOutput(BaseModel):
    """Structured output of the `register_procedure` MCP tool."""

    procedure_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_procedure` tool on the given MCP server."""

    @mcp.tool(
        name="register_procedure",
        description=(
            "Register a new episodic operational procedure (bakeout, "
            "calibration, alignment, recovery, beam-mode change, etc.). "
            "Procedure lands in 'Defined' status; operator transitions "
            "to 'Running' via 'start_procedure' (10c-b)."
        ),
    )
    async def register_procedure_tool(  # pyright: ignore[reportUnusedFunction]
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=PROCEDURE_NAME_MAX_LENGTH,
                description="Operator-readable display name for the procedure.",
            ),
        ],
        kind: Annotated[
            str,
            Field(
                min_length=1,
                max_length=PROCEDURE_KIND_MAX_LENGTH,
                description=(
                    "Free-form ISA-106 procedure-kind discriminator "
                    "(bakeout, calibration, alignment, etc.)."
                ),
            ),
        ],
        target_asset_ids: Annotated[
            list[UUID] | None,
            Field(
                description=(
                    "Asset ids this procedure acts on. None / empty list "
                    "valid for facility-envelope procedures."
                ),
            ),
        ] = None,
        parent_run_id: Annotated[
            UUID | None,
            Field(
                description=(
                    "Optional parent Run binding. None = standalone procedure; UUID = Phase-of-Run."
                ),
            ),
        ] = None,
        capability_id: Annotated[
            UUID | None,
            Field(
                description=(
                    "Optional Capability template binding (Phase 10d-additive). "
                    "When supplied, the bound Capability must declare "
                    "`Procedure` in its executor_shapes set."
                ),
            ),
        ] = None,
    ) -> RegisterProcedureOutput:
        handler = get_handler()
        procedure_id = await handler(
            RegisterProcedure(
                name=name,
                kind=kind,
                target_asset_ids=frozenset(target_asset_ids or []),
                parent_run_id=parent_run_id,
                capability_id=capability_id,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterProcedureOutput(procedure_id=procedure_id)
