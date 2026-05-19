"""MCP tool for the `update_method_parameters_schema` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.features.update_method_parameters_schema.command import (
    UpdateMethodParametersSchema,
)
from cora.recipe.features.update_method_parameters_schema.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `update_method_parameters_schema` MCP tool."""

    @mcp.tool(
        name="update_method_parameters_schema",
        description=(
            "Set, replace, or clear a Method's parameters_schema "
            "(JSON Schema Draft 2020-12, constrained subset). The "
            "schema declares the shape of parameter dicts that "
            "downstream Plans (6g-b) and Runs (6g-c) carry for this "
            "Method. Pass null for parameters_schema to clear an "
            "existing declaration. Phase 6g-a: pre-positions for "
            "Plan defaults + Run override validation in 6g-b/6g-c."
        ),
    )
    async def update_method_parameters_schema_tool(  # pyright: ignore[reportUnusedFunction]
        method_id: Annotated[UUID, Field(description="Target method's id.")],
        parameters_schema: Annotated[
            dict[str, Any] | None,
            Field(
                description=(
                    "JSON Schema (Draft 2020-12 subset) or null to clear. "
                    "Required keys when present: $schema "
                    "(https://json-schema.org/draft/2020-12/schema). "
                    "Subset: type, required, properties, enum, minimum, "
                    "maximum, pattern."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            UpdateMethodParametersSchema(
                method_id=method_id,
                parameters_schema=parameters_schema,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
