"""MCP tool for the `version_plan` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.aggregates.plan import PLAN_VERSION_TAG_MAX_LENGTH
from cora.recipe.features.version_plan.command import VersionPlan
from cora.recipe.features.version_plan.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `version_plan` tool on the given MCP server."""

    @mcp.tool(
        name="version_plan",
        description=(
            "Issue a new version label for an existing plan. "
            "Accepts both Defined and Versioned source states "
            "(subsequent revisions allowed). Deprecated plans "
            "cannot be re-versioned."
        ),
    )
    async def version_plan_tool(  # pyright: ignore[reportUnusedFunction]
        plan_id: Annotated[
            UUID,
            Field(description="Target plan's id."),
        ],
        version_tag: Annotated[
            str,
            Field(
                min_length=1,
                max_length=PLAN_VERSION_TAG_MAX_LENGTH,
                description=(
                    "Operator-supplied label for this revision (for example 'v2', '2026-Q3')."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            VersionPlan(plan_id=plan_id, version_tag=version_tag),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
