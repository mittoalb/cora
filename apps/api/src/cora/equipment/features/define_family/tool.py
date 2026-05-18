"""MCP tool for the `define_family` slice.

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

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.aggregates.family import FAMILY_NAME_MAX_LENGTH, Affordance
from cora.equipment.features.define_family.command import DefineFamily
from cora.equipment.features.define_family.handler import IdempotentHandler
from cora.infrastructure.observability import current_correlation_id


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
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return DefineFamilyOutput(family_id=family_id)
