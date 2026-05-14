"""MCP tool for the `update_plan_parameter_defaults` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.infrastructure.observability import current_correlation_id
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.features.update_plan_parameter_defaults.command import (
    UpdatePlanParameterDefaults,
)
from cora.recipe.features.update_plan_parameter_defaults.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `update_plan_parameter_defaults` MCP tool."""

    @mcp.tool(
        name="update_plan_parameter_defaults",
        description=(
            "Update a Plan's parameter_defaults dict with RFC 7396 "
            "(JSON Merge Patch) semantics. Non-null values set/replace; "
            "null values delete; absent keys are preserved. The merged "
            "result is validated against the owning Method's "
            "parameters_schema (6g-a); validation is permissive when "
            "the Method declares no schema. Phase 6g-b: pre-positions "
            "Run.parameter_overrides + effective_parameters resolution "
            "in 6g-c."
        ),
    )
    async def update_plan_parameter_defaults_tool(  # pyright: ignore[reportUnusedFunction]
        plan_id: Annotated[UUID, Field(description="Target plan's id.")],
        parameter_defaults_patch: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Partial parameter_defaults dict. RFC 7396 merge "
                    "semantics: non-null values set/replace; null "
                    "values delete; absent keys are preserved."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            UpdatePlanParameterDefaults(
                plan_id=plan_id, parameter_defaults_patch=parameter_defaults_patch
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
