"""MCP tool for the `define_practice` slice.

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
from cora.recipe.aggregates.practice import PRACTICE_NAME_MAX_LENGTH
from cora.recipe.features.define_practice.command import DefinePractice
from cora.recipe.features.define_practice.handler import IdempotentHandler


class DefinePracticeOutput(BaseModel):
    """Structured output of the `define_practice` MCP tool."""

    practice_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_practice` tool on the given MCP server."""

    @mcp.tool(
        name="define_practice",
        description=(
            "Define a new facility-adapted Method (Practice). "
            "method_id is the Method this Practice adapts; site_id is "
            "the Site-level Asset this Practice belongs to. Both are "
            "eventual-consistency refs (existence not verified)."
        ),
    )
    async def define_practice_tool(  # pyright: ignore[reportUnusedFunction]
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=PRACTICE_NAME_MAX_LENGTH,
                description="Display name for the new practice.",
            ),
        ],
        method_id: Annotated[
            UUID,
            Field(description="Method id this Practice adapts."),
        ],
        site_id: Annotated[
            UUID,
            Field(description="Site-level Asset id this Practice belongs to."),
        ],
    ) -> DefinePracticeOutput:
        handler = get_handler()
        practice_id = await handler(
            DefinePractice(name=name, method_id=method_id, site_id=site_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return DefinePracticeOutput(practice_id=practice_id)
