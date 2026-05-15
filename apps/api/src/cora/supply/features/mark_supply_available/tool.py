"""MCP tool for the `mark_supply_available` slice.

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
from cora.supply._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.supply.aggregates.supply import SUPPLY_REASON_MAX_LENGTH
from cora.supply.features.mark_supply_available.command import MarkSupplyAvailable
from cora.supply.features.mark_supply_available.handler import Handler


class MarkSupplyAvailableOutput(BaseModel):
    """Structured output of the `mark_supply_available` MCP tool."""

    supply_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `mark_supply_available` tool on the given MCP server."""

    @mcp.tool(
        name="mark_supply_available",
        description=(
            "Operator declares a registered Supply Available for the first "
            "time (Unknown -> Available). Single-source: requires Supply to "
            "be in 'Unknown' status. For recovery acknowledgement after a "
            "Recovering state, use 'restore_supply' (10a-b)."
        ),
    )
    async def mark_supply_available_tool(  # pyright: ignore[reportUnusedFunction]
        supply_id: Annotated[
            UUID,
            Field(description="Target supply's id."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=SUPPLY_REASON_MAX_LENGTH,
                description=(
                    "Operator-supplied reason for declaring the supply Available "
                    "for the first time (audit-log breadcrumb)."
                ),
            ),
        ],
    ) -> MarkSupplyAvailableOutput:
        handler = get_handler()
        await handler(
            MarkSupplyAvailable(supply_id=supply_id, reason=reason),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return MarkSupplyAvailableOutput(supply_id=supply_id)
