"""MCP tool for the `mark_supply_recovering` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.supply._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.supply.aggregates.supply import SUPPLY_REASON_MAX_LENGTH
from cora.supply.features.mark_supply_recovering.command import MarkSupplyRecovering
from cora.supply.features.mark_supply_recovering.handler import Handler


class MarkSupplyRecoveringOutput(BaseModel):
    """Structured output of the `mark_supply_recovering` MCP tool."""

    supply_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `mark_supply_recovering` tool on the given MCP server."""

    @mcp.tool(
        name="mark_supply_recovering",
        description=(
            "Mark a Supply as Recovering (observation suggests it may be "
            "coming back). Single-source: only an Unavailable supply can "
            "be marked Recovering. Recovery -> Available requires an "
            "explicit `restore_supply` (operator acknowledgement)."
        ),
    )
    async def mark_supply_recovering_tool(  # pyright: ignore[reportUnusedFunction]
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
                    "Operator-supplied reason for the mark-recovering transition "
                    "(audit-log breadcrumb)."
                ),
            ),
        ],
    ) -> MarkSupplyRecoveringOutput:
        handler = get_handler()
        await handler(
            MarkSupplyRecovering(supply_id=supply_id, reason=reason),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return MarkSupplyRecoveringOutput(supply_id=supply_id)
