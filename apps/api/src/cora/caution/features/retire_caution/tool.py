"""MCP tool for the `retire_caution` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.caution.aggregates.caution import CautionRetireReason
from cora.caution.features.retire_caution.command import RetireCaution
from cora.caution.features.retire_caution.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


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
        ctx: Context[Any, Any, Any],
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
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RetireCautionOutput(caution_id=caution_id)
