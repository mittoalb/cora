"""MCP tool for the `get_plan` query slice.

Surfaces the same handler the REST route uses. Returns a structured
PlanOutput on hit. On miss raises an exception that FastMCP wraps
as `isError: true` with a text diagnostic — matches the REST 404
behaviour in MCP's error idiom.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.aggregates.plan import PLAN_NAME_MAX_LENGTH
from cora.recipe.features.get_plan.handler import Handler
from cora.recipe.features.get_plan.query import GetPlan


class PlanOutput(BaseModel):
    """Structured output of the `get_plan` MCP tool.

    `created_at` / `versioned_at` / `deprecated_at` mirror the REST
    `PlanResponse` (Path C, audit-2026-05-20 Iter B-1): sourced from
    the `proj_recipe_plan_summary` projection. Null semantics: read
    together with `status` — a populated `status` with a null
    timestamp means the projection has not yet folded that lifecycle
    event (transient eventual-consistency window), never a missing
    transition. A not-found Plan raises (MCP `isError: true`) rather
    than returning null timestamps.
    """

    id: UUID
    name: str = Field(..., max_length=PLAN_NAME_MAX_LENGTH)
    practice_id: UUID
    asset_ids: list[UUID]
    status: str
    version: str | None
    created_at: datetime | None = None
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_plan` tool on the given MCP server."""

    @mcp.tool(
        name="get_plan",
        description="Read the current state of an existing plan by id.",
    )
    async def get_plan_tool(  # pyright: ignore[reportUnusedFunction]
        plan_id: Annotated[
            UUID,
            Field(description="Target plan's id."),
        ],
    ) -> PlanOutput:
        handler = get_handler()
        view = await handler(
            GetPlan(plan_id=plan_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if view is None:
            msg = f"Plan {plan_id} not found"
            raise ValueError(msg)
        plan = view.plan
        timestamps = view.timestamps
        return PlanOutput(
            id=plan.id,
            name=plan.name.value,
            practice_id=plan.practice_id,
            asset_ids=sorted(plan.asset_ids, key=str),
            status=plan.status.value,
            version=plan.version,
            created_at=timestamps.created_at if timestamps is not None else None,
            versioned_at=timestamps.versioned_at if timestamps is not None else None,
            deprecated_at=timestamps.deprecated_at if timestamps is not None else None,
        )
