"""MCP tool for the `get_capability` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment.aggregates.family import Affordance
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.aggregates.capability import (
    CAPABILITY_CODE_MAX_LENGTH,
    CAPABILITY_NAME_MAX_LENGTH,
    ExecutorShape,
)
from cora.recipe.features.get_capability.handler import Handler
from cora.recipe.features.get_capability.query import GetCapability


class CapabilityOutput(BaseModel):
    """Structured output of the `get_capability` MCP tool.

    `created_at` / `versioned_at` / `deprecated_at` mirror the REST
    `CapabilityResponse` (Path C): sourced
    from the `proj_recipe_capability_summary` projection. Null
    semantics: read together with `status`: a populated `status`
    with a null timestamp means the projection has not yet folded
    that lifecycle event, never a missing transition. A not-found
    Capability raises (MCP `isError: true`) rather than returning
    null timestamps.
    """

    id: UUID
    code: str = Field(..., max_length=CAPABILITY_CODE_MAX_LENGTH)
    name: str = Field(..., max_length=CAPABILITY_NAME_MAX_LENGTH)
    status: str
    version: str | None
    description: str | None
    required_affordances: list[Affordance]
    executor_shapes: list[ExecutorShape]
    parameters_schema: dict[str, Any] | None
    replaced_by_capability_id: UUID | None
    created_at: datetime | None = None
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_capability` tool on the given MCP server."""

    @mcp.tool(
        name="get_capability",
        description="Read the current state of an existing Capability by id.",
    )
    async def get_capability_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        capability_id: Annotated[
            UUID,
            Field(description="Target Capability's id."),
        ],
    ) -> CapabilityOutput:
        handler = get_handler()
        view = await handler(
            GetCapability(capability_id=capability_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if view is None:
            msg = f"Capability {capability_id} not found"
            raise ValueError(msg)
        capability = view.capability
        timestamps = view.timestamps
        return CapabilityOutput(
            id=capability.id,
            code=capability.code.value,
            name=capability.name.value,
            status=capability.status.value,
            version=capability.version,
            description=capability.description,
            required_affordances=sorted(capability.required_affordances, key=lambda a: a.value),
            executor_shapes=sorted(capability.executor_shapes, key=lambda s: s.value),
            parameters_schema=capability.parameters_schema,
            replaced_by_capability_id=capability.replaced_by_capability_id,
            created_at=timestamps.created_at if timestamps is not None else None,
            versioned_at=timestamps.versioned_at if timestamps is not None else None,
            deprecated_at=timestamps.deprecated_at if timestamps is not None else None,
        )
