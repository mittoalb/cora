"""MCP tool for the `get_capability` query slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.equipment.aggregates.family import Affordance
from cora.infrastructure.observability import current_correlation_id
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.aggregates.capability import (
    CAPABILITY_CODE_MAX_LENGTH,
    CAPABILITY_NAME_MAX_LENGTH,
    ExecutorShape,
)
from cora.recipe.features.get_capability.handler import Handler
from cora.recipe.features.get_capability.query import GetCapability


class CapabilityOutput(BaseModel):
    """Structured output of the `get_capability` MCP tool."""

    id: UUID
    code: str = Field(..., max_length=CAPABILITY_CODE_MAX_LENGTH)
    name: str = Field(..., max_length=CAPABILITY_NAME_MAX_LENGTH)
    status: str
    version: str | None
    description: str | None
    required_affordances: list[Affordance]
    executor_shapes: list[ExecutorShape]
    parameter_schema: dict[str, Any] | None
    replaced_by_capability_id: UUID | None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_capability` tool on the given MCP server."""

    @mcp.tool(
        name="get_capability",
        description="Read the current state of an existing Capability by id.",
    )
    async def get_capability_tool(  # pyright: ignore[reportUnusedFunction]
        capability_id: Annotated[
            UUID,
            Field(description="Target Capability's id."),
        ],
    ) -> CapabilityOutput:
        handler = get_handler()
        capability = await handler(
            GetCapability(capability_id=capability_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        if capability is None:
            msg = f"Capability {capability_id} not found"
            raise ValueError(msg)
        return CapabilityOutput(
            id=capability.id,
            code=capability.code.value,
            name=capability.name.value,
            status=capability.status.value,
            version=capability.version,
            description=capability.description,
            required_affordances=sorted(capability.required_affordances, key=lambda a: a.value),
            executor_shapes=sorted(capability.executor_shapes, key=lambda s: s.value),
            parameter_schema=capability.parameter_schema,
            replaced_by_capability_id=capability.replaced_by_capability_id,
        )
