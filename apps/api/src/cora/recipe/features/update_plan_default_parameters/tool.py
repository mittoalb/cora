"""MCP tool for the `update_plan_default_parameters` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.features.update_plan_default_parameters.command import (
    UpdatePlanDefaultParameters,
)
from cora.recipe.features.update_plan_default_parameters.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `update_plan_default_parameters` MCP tool."""

    @mcp.tool(
        name="update_plan_default_parameters",
        description=(
            "Update a Plan's default_parameters dict with RFC 7396 "
            "(JSON Merge Patch) semantics. Non-null values set/replace; "
            "null values delete; absent keys are preserved. The merged "
            "result is validated against the owning Method's "
            "parameters_schema (6g-a); STRICT when the Method declares "
            "no schema (non-empty defaults rejected; declare an empty "
            "`{}` schema for parameter-less Methods, or omit defaults). "
            "Pre-positions Run.override_parameters + "
            "effective_parameters resolution."
        ),
    )
    async def update_plan_default_parameters_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        plan_id: Annotated[UUID, Field(description="Target plan's id.")],
        default_parameters_patch: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Partial default_parameters dict. RFC 7396 merge "
                    "semantics: non-null values set/replace; null "
                    "values delete; absent keys are preserved."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            UpdatePlanDefaultParameters(
                plan_id=plan_id, default_parameters_patch=default_parameters_patch
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
