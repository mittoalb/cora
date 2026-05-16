"""MCP tool for the `retire_caution` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.caution._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.caution.aggregates.caution import CautionRetireReason
from cora.caution.features.retire_caution.command import RetireCaution
from cora.caution.features.retire_caution.handler import Handler
from cora.infrastructure.observability import current_correlation_id


class RetireCautionOutput(BaseModel):
    """Structured output of the `retire_caution` MCP tool."""

    caution_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `retire_caution` tool on the given MCP server."""

    @mcp.tool(
        name="retire_caution",
        description=(
            "Retire an Active caution (Active -> Retired). Terminal-good: "
            "retired cautions cannot be revived. Single-source from Active. "
            "Closed reason enum: Resolved, NoLongerApplies, WrongTarget."
        ),
    )
    async def retire_caution_tool(  # pyright: ignore[reportUnusedFunction]
        caution_id: Annotated[UUID, Field(description="Target caution's id.")],
        reason: Annotated[
            CautionRetireReason,
            Field(description="Closed reason enum."),
        ],
    ) -> RetireCautionOutput:
        handler = get_handler()
        await handler(
            RetireCaution(
                caution_id=caution_id,
                reason=reason,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return RetireCautionOutput(caution_id=caution_id)
