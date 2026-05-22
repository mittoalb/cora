"""MCP tool for the `get_family` query slice.

Surfaces the same handler the REST route uses. Returns a structured
FamilyOutput on hit. On miss raises an exception that FastMCP
wraps as `isError: true` with a text diagnostic — matches the REST
404 behaviour in MCP's error idiom (LLM consumers get a clear
"family not found" message rather than null structuredContent
they have to interpret).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment.aggregates.family import FAMILY_NAME_MAX_LENGTH, Affordance
from cora.equipment.features.get_family.handler import Handler
from cora.equipment.features.get_family.query import GetFamily
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class FamilyOutput(BaseModel):
    """Structured output of the `get_family` MCP tool.

    `created_at` / `versioned_at` / `deprecated_at` mirror the REST
    `FamilyResponse` (Path C): sourced
    from the `proj_equipment_family_summary` projection. Null
    semantics: read together with `status` — a populated `status`
    with a null timestamp means the projection has not yet folded
    that lifecycle event, never a missing transition. A not-found
    Family raises (MCP `isError: true`) rather than returning null
    timestamps.
    """

    id: UUID
    name: str = Field(..., max_length=FAMILY_NAME_MAX_LENGTH)
    status: str
    version: str | None
    affordances: list[Affordance]
    created_at: datetime | None = None
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_family` tool on the given MCP server."""

    @mcp.tool(
        name="get_family",
        description="Read the current state of an existing family by id.",
    )
    async def get_family_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        family_id: Annotated[
            UUID,
            Field(description="Target family's id."),
        ],
    ) -> FamilyOutput:
        handler = get_handler()
        view = await handler(
            GetFamily(family_id=family_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if view is None:
            msg = f"Family {family_id} not found"
            raise ValueError(msg)
        family = view.family
        timestamps = view.timestamps
        return FamilyOutput(
            id=family.id,
            name=family.name.value,
            status=family.status.value,
            version=family.version,
            affordances=sorted(family.affordances, key=lambda a: a.value),
            created_at=timestamps.created_at if timestamps is not None else None,
            versioned_at=timestamps.versioned_at if timestamps is not None else None,
            deprecated_at=timestamps.deprecated_at if timestamps is not None else None,
        )
