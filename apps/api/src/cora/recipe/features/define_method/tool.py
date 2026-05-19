"""MCP tool for the `define_method` slice.

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
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.aggregates.method import (
    METHOD_NAME_MAX_LENGTH,
    METHOD_NEEDS_SUPPLY_KIND_MAX_LENGTH,
)
from cora.recipe.features.define_method.command import DefineMethod
from cora.recipe.features.define_method.handler import IdempotentHandler


class DefineMethodOutput(BaseModel):
    """Structured output of the `define_method` MCP tool."""

    method_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_method` tool on the given MCP server."""

    @mcp.tool(
        name="define_method",
        description=(
            "Define a new abstract technique-class recipe (Method). "
            "needed_families is a list of Family ids the Method "
            "requires; may be empty for purely procedural Methods. "
            "needed_supplies (Phase 10b) is a list of Supply.kind STRINGS "
            "(for example 'PhotonBeam', 'LiquidNitrogen'); may be empty."
        ),
    )
    async def define_method_tool(  # pyright: ignore[reportUnusedFunction]
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=METHOD_NAME_MAX_LENGTH,
                description="Display name for the new method.",
            ),
        ],
        capability_id: Annotated[
            UUID,
            Field(
                description=(
                    "Universal Capability template this Method realizes. "
                    "REQUIRED per Pattern P (6l-strict). The bound "
                    "Capability must declare `Method` in its "
                    "executor_shapes set; otherwise 409."
                ),
            ),
        ],
        needed_families: Annotated[
            list[UUID],
            Field(
                description=(
                    "Family ids this Method requires. May be empty. "
                    "Eventual-consistency: ids are NOT verified against "
                    "the Family stream at decide time."
                ),
            ),
        ],
        needed_supplies: Annotated[
            list[
                Annotated[
                    str,
                    Field(
                        min_length=1,
                        max_length=METHOD_NEEDS_SUPPLY_KIND_MAX_LENGTH,
                    ),
                ]
            ],
            Field(
                description=(
                    "Supply.kind strings this Method requires (NOT Supply "
                    "instance UUIDs). May be empty. Eventual-consistency: "
                    "kinds are NOT verified against the Supply stream."
                ),
            ),
        ]
        | None = None,
    ) -> DefineMethodOutput:
        handler = get_handler()
        method_id = await handler(
            DefineMethod(
                name=name,
                capability_id=capability_id,
                needed_families=frozenset(needed_families),
                needed_supplies=frozenset(needed_supplies or []),
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefineMethodOutput(method_id=method_id)
