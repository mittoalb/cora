"""MCP tool for the `define_capability` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.equipment.aggregates.family import Affordance
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.aggregates.capability import (
    CAPABILITY_CODE_MAX_LENGTH,
    CAPABILITY_DESCRIPTION_MAX_LENGTH,
    CAPABILITY_NAME_MAX_LENGTH,
    ExecutorShape,
)
from cora.recipe.features.define_capability.command import DefineCapability
from cora.recipe.features.define_capability.handler import IdempotentHandler


class DefineCapabilityOutput(BaseModel):
    """Structured output of the `define_capability` MCP tool."""

    capability_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_capability` tool on the given MCP server."""

    @mcp.tool(
        name="define_capability",
        description=(
            "Define a new universal Capability template at the operations "
            "layer. Capability sits above heterogeneous executor shapes "
            "(Method-chain for science, Procedure for ceremony) and "
            "declares the Family.affordance contract any implementer "
            "must satisfy + the executor kinds that may implement it."
        ),
    )
    async def define_capability_tool(  # pyright: ignore[reportUnusedFunction]
        code: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CAPABILITY_CODE_MAX_LENGTH,
                description=(
                    "Namespaced code under `cora.capability.*` (closed core) "
                    "or `cora.capability.<facility>.*` (facility extension)."
                ),
            ),
        ],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CAPABILITY_NAME_MAX_LENGTH,
                description="Display name for the new Capability.",
            ),
        ],
        required_affordances: Annotated[
            list[Affordance],
            Field(
                description=(
                    "Family.affordance contract any implementer must satisfy. "
                    "Required; supply `[]` explicitly when the Capability is "
                    "parameter-driven without an affordance requirement."
                ),
            ),
        ],
        executor_shapes: Annotated[
            list[ExecutorShape],
            Field(
                description=(
                    "Closed-enum set of executor kinds that may implement "
                    "this Capability ({Method, Procedure} at v1). Required "
                    "non-empty."
                ),
            ),
        ],
        description: Annotated[
            str | None,
            Field(
                default=None,
                max_length=CAPABILITY_DESCRIPTION_MAX_LENGTH,
                description="Optional human description (0-2000 chars).",
            ),
        ] = None,
        parameter_schema: Annotated[
            dict[str, Any] | None,
            Field(
                default=None,
                description=(
                    "Optional declarative JSON Schema (constrained subset) "
                    "for the parameter contract. Method.parameters_schema "
                    "must validate as a subset at define_method time."
                ),
            ),
        ] = None,
    ) -> DefineCapabilityOutput:
        handler = get_handler()
        capability_id = await handler(
            DefineCapability(
                code=code,
                name=name,
                description=description,
                required_affordances=frozenset(required_affordances),
                executor_shapes=frozenset(executor_shapes),
                parameter_schema=parameter_schema,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefineCapabilityOutput(capability_id=capability_id)
