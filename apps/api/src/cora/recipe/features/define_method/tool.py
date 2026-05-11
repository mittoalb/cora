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
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.aggregates.method import METHOD_NAME_MAX_LENGTH
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
            "needs_capabilities is a list of Capability ids the Method "
            "requires; may be empty for purely procedural Methods."
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
        needs_capabilities: Annotated[
            list[UUID],
            Field(
                description=(
                    "Capability ids this Method requires. May be empty. "
                    "Eventual-consistency: ids are NOT verified against "
                    "the Capability stream at decide time."
                ),
            ),
        ],
    ) -> DefineMethodOutput:
        handler = get_handler()
        method_id = await handler(
            DefineMethod(
                name=name,
                needs_capabilities=frozenset(needs_capabilities),
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return DefineMethodOutput(method_id=method_id)
