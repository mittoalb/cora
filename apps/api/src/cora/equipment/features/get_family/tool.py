"""MCP tool for the `get_family` query slice.

Surfaces the same handler the REST route uses. Returns a structured
FamilyOutput on hit. On miss raises an exception that FastMCP
wraps as `isError: true` with a text diagnostic — matches the REST
404 behaviour in MCP's error idiom (LLM consumers get a clear
"family not found" message rather than null structuredContent
they have to interpret).
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.aggregates.family import FAMILY_NAME_MAX_LENGTH, Affordance
from cora.equipment.features.get_family.handler import Handler
from cora.equipment.features.get_family.query import GetFamily
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class FamilyOutput(BaseModel):
    """Structured output of the `get_family` MCP tool."""

    id: UUID
    name: str = Field(..., max_length=FAMILY_NAME_MAX_LENGTH)
    status: str
    version: str | None
    affordances: list[Affordance]


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_family` tool on the given MCP server."""

    @mcp.tool(
        name="get_family",
        description="Read the current state of an existing family by id.",
    )
    async def get_family_tool(  # pyright: ignore[reportUnusedFunction]
        family_id: Annotated[
            UUID,
            Field(description="Target family's id."),
        ],
    ) -> FamilyOutput:
        handler = get_handler()
        family = await handler(
            GetFamily(family_id=family_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if family is None:
            msg = f"Family {family_id} not found"
            raise ValueError(msg)
        return FamilyOutput(
            id=family.id,
            name=family.name.value,
            status=family.status.value,
            version=family.version,
            affordances=sorted(family.affordances, key=lambda a: a.value),
        )
