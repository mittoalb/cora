"""MCP tool for the `register_supply` slice.

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
from cora.supply.aggregates.supply import (
    SUPPLY_KIND_MAX_LENGTH,
    SUPPLY_NAME_MAX_LENGTH,
    SupplyScope,
)
from cora.supply.features.register_supply.command import RegisterSupply
from cora.supply.features.register_supply.handler import IdempotentHandler


class RegisterSupplyOutput(BaseModel):
    """Structured output of the `register_supply` MCP tool."""

    supply_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_supply` tool on the given MCP server."""

    @mcp.tool(
        name="register_supply",
        description=(
            "Register a new continuously-available resource (photon beam, LN2, "
            "compressed air, electrical power, vacuum, process gas, compute pool, "
            "etc.). Supply lands in 'Unknown' status; operator confirms first "
            "observation via 'mark_supply_available'."
        ),
    )
    async def register_supply_tool(  # pyright: ignore[reportUnusedFunction]
        scope: Annotated[
            SupplyScope,
            Field(
                description=(
                    "Hierarchical scope (Facility / Sector / Beamline) at which "
                    "the supply is provisioned."
                ),
            ),
        ],
        kind: Annotated[
            str,
            Field(
                min_length=1,
                max_length=SUPPLY_KIND_MAX_LENGTH,
                description=(
                    "Free-form supply-kind discriminator (PhotonBeam, "
                    "LiquidNitrogen, CompressedAir, etc.)."
                ),
            ),
        ],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=SUPPLY_NAME_MAX_LENGTH,
                description="Operator-readable display name for this Supply instance.",
            ),
        ],
    ) -> RegisterSupplyOutput:
        handler = get_handler()
        supply_id = await handler(
            RegisterSupply(scope=scope, kind=kind, name=name),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return RegisterSupplyOutput(supply_id=supply_id)
