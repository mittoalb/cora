"""MCP tool for the `define_family` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment.aggregates.family import FAMILY_NAME_MAX_LENGTH, Affordance
from cora.equipment.features.define_family.command import DefineFamily
from cora.equipment.features.define_family.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class DefineFamilyOutput(BaseModel):
    """Structured output of the `define_family` MCP tool."""

    family_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_family` tool on the given MCP server."""

    @mcp.tool(
        name="define_family",
        description=(
            "Define a new device-class Family with the given display name and affordance set."
        ),
    )
    async def define_family_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=FAMILY_NAME_MAX_LENGTH,
                description="Display name for the new Family.",
            ),
        ],
        affordances: Annotated[
            list[Affordance],
            Field(
                description=(
                    "Closed-enum set of device-level operational primitives "
                    "this Family supports. Required; supply `[]` explicitly "
                    "when no v1 Affordance applies."
                ),
            ),
        ],
    ) -> DefineFamilyOutput:
        handler = get_handler()
        family_id = await handler(
            DefineFamily(name=name, affordances=frozenset(affordances)),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefineFamilyOutput(family_id=family_id)
