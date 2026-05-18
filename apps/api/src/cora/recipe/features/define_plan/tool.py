"""MCP tool for the `define_plan` slice.

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
from cora.recipe.aggregates.plan import PLAN_NAME_MAX_LENGTH
from cora.recipe.features.define_plan.command import DefinePlan
from cora.recipe.features.define_plan.handler import IdempotentHandler


class DefinePlanOutput(BaseModel):
    """Structured output of the `define_plan` MCP tool."""

    plan_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_plan` tool on the given MCP server."""

    @mcp.tool(
        name="define_plan",
        description=(
            "Define a new Plan: bind a Practice to a set of Asset "
            "instances. Validates at bind time that the Practice and "
            "its Method are not Deprecated, that no bound Asset is "
            "Decommissioned, and that the union of bound Assets' "
            "families covers the Method's needed_families."
        ),
    )
    async def define_plan_tool(  # pyright: ignore[reportUnusedFunction]
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=PLAN_NAME_MAX_LENGTH,
                description="Display name for the new plan.",
            ),
        ],
        practice_id: Annotated[
            UUID,
            Field(description="Practice id this Plan binds."),
        ],
        asset_ids: Annotated[
            set[UUID],
            Field(
                min_length=1,
                description=("Set of Asset ids this Plan binds. At least one required."),
            ),
        ],
    ) -> DefinePlanOutput:
        handler = get_handler()
        plan_id = await handler(
            DefinePlan(
                name=name,
                practice_id=practice_id,
                asset_ids=frozenset(asset_ids),
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return DefinePlanOutput(plan_id=plan_id)
