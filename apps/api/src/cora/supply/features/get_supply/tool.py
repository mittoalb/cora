"""MCP tool for the `get_supply` query slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.supply.aggregates.supply import (
    SUPPLY_KIND_MAX_LENGTH,
    SUPPLY_NAME_MAX_LENGTH,
    SupplyScope,
    SupplyStatus,
)
from cora.supply.features.get_supply.handler import Handler
from cora.supply.features.get_supply.query import GetSupply


class SupplyOutput(BaseModel):
    """Structured output of the `get_supply` MCP tool (on hit).

    On miss the tool raises `ValueError` so FastMCP wraps the
    response as `isError: true` with a clear diagnostic — same
    convention as `get_family` / `get_asset`. Never returns
    None; the LLM gets either a populated DTO or an error.
    """

    id: UUID
    scope: SupplyScope
    kind: str = Field(..., max_length=SUPPLY_KIND_MAX_LENGTH)
    name: str = Field(..., max_length=SUPPLY_NAME_MAX_LENGTH)
    status: SupplyStatus


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_supply` tool on the given MCP server."""

    @mcp.tool(
        name="get_supply",
        description=(
            "Look up a supply by id. Returns scope, kind, name, and "
            "current FSM status (Unknown / Available / Degraded / "
            "Unavailable / Recovering)."
        ),
    )
    async def get_supply_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        supply_id: Annotated[
            UUID,
            Field(description="Target supply's id."),
        ],
    ) -> SupplyOutput:
        handler = get_handler()
        supply = await handler(
            GetSupply(supply_id=supply_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if supply is None:
            msg = f"Supply {supply_id} not found"
            raise ValueError(msg)
        return SupplyOutput(
            id=supply.id,
            scope=supply.scope,
            kind=supply.kind,
            name=supply.name.value,
            status=supply.status,
        )
