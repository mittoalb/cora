"""MCP tool for the `get_practice` query slice.

Surfaces the same handler the REST route uses. Returns a structured
PracticeOutput on hit. On miss raises an exception that FastMCP
wraps as `isError: true` with a text diagnostic.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.aggregates.practice import PRACTICE_NAME_MAX_LENGTH
from cora.recipe.features.get_practice.handler import Handler
from cora.recipe.features.get_practice.query import GetPractice


class PracticeOutput(BaseModel):
    """Structured output of the `get_practice` MCP tool.

    `created_at` / `versioned_at` / `deprecated_at` mirror the REST
    `PracticeResponse` (Path C): sourced
    from the `proj_recipe_practice_summary` projection. Null
    semantics: read together with `status` — a populated `status`
    with a null timestamp means the projection has not yet folded
    that lifecycle event, never a missing transition. A not-found
    Practice raises (MCP `isError: true`) rather than returning null
    timestamps.
    """

    id: UUID
    name: str = Field(..., max_length=PRACTICE_NAME_MAX_LENGTH)
    method_id: UUID
    site_id: UUID
    status: str
    version: str | None
    created_at: datetime | None = None
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_practice` tool on the given MCP server."""

    @mcp.tool(
        name="get_practice",
        description="Read the current state of an existing practice by id.",
    )
    async def get_practice_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        practice_id: Annotated[
            UUID,
            Field(description="Target practice's id."),
        ],
    ) -> PracticeOutput:
        handler = get_handler()
        view = await handler(
            GetPractice(practice_id=practice_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if view is None:
            msg = f"Practice {practice_id} not found"
            raise ValueError(msg)
        practice = view.practice
        timestamps = view.timestamps
        return PracticeOutput(
            id=practice.id,
            name=practice.name.value,
            method_id=practice.method_id,
            site_id=practice.site_id,
            status=practice.status.value,
            version=practice.version,
            created_at=timestamps.created_at if timestamps is not None else None,
            versioned_at=timestamps.versioned_at if timestamps is not None else None,
            deprecated_at=timestamps.deprecated_at if timestamps is not None else None,
        )
