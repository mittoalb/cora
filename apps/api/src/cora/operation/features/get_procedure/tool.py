"""MCP tool for the `get_procedure` query slice.

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
from cora.operation._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.operation.aggregates.procedure import (
    PROCEDURE_KIND_MAX_LENGTH,
    PROCEDURE_NAME_MAX_LENGTH,
    ProcedureStatus,
)
from cora.operation.features.get_procedure.handler import Handler
from cora.operation.features.get_procedure.query import GetProcedure


class ProcedureOutput(BaseModel):
    """Structured output of the `get_procedure` MCP tool (on hit).

    On miss the tool raises `ValueError` so FastMCP wraps the
    response as `isError: true` with a clear diagnostic -- same
    convention as `get_family` / `get_asset` / `get_supply`.
    Never returns None; the LLM gets either a populated DTO or an
    error.
    """

    id: UUID
    name: str = Field(..., max_length=PROCEDURE_NAME_MAX_LENGTH)
    kind: str = Field(..., max_length=PROCEDURE_KIND_MAX_LENGTH)
    target_asset_ids: list[UUID]
    status: ProcedureStatus
    parent_run_id: UUID | None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_procedure` tool on the given MCP server."""

    @mcp.tool(
        name="get_procedure",
        description=(
            "Look up a procedure by id. Returns name, kind, target "
            "Asset ids, current FSM status (Defined / Running / "
            "Completed / Aborted / Truncated), and optional parent "
            "Run binding."
        ),
    )
    async def get_procedure_tool(  # pyright: ignore[reportUnusedFunction]
        procedure_id: Annotated[
            UUID,
            Field(description="Target procedure's id."),
        ],
    ) -> ProcedureOutput:
        handler = get_handler()
        procedure = await handler(
            GetProcedure(procedure_id=procedure_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        if procedure is None:
            msg = f"Procedure {procedure_id} not found"
            raise ValueError(msg)
        return ProcedureOutput(
            id=procedure.id,
            name=procedure.name.value,
            kind=procedure.kind,
            target_asset_ids=sorted(procedure.target_asset_ids, key=str),
            status=procedure.status,
            parent_run_id=procedure.parent_run_id,
        )
