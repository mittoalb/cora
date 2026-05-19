"""MCP tool for the `get_method` query slice.

Surfaces the same handler the REST route uses. Returns a structured
MethodOutput on hit. On miss raises an exception that FastMCP wraps
as `isError: true` with a text diagnostic — matches the REST 404
behaviour in MCP's error idiom (LLM consumers get a clear "method
not found" message rather than null structuredContent they have to
interpret).
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.aggregates.method import METHOD_NAME_MAX_LENGTH
from cora.recipe.features.get_method.handler import Handler
from cora.recipe.features.get_method.query import GetMethod


class MethodOutput(BaseModel):
    """Structured output of the `get_method` MCP tool."""

    id: UUID
    name: str = Field(..., max_length=METHOD_NAME_MAX_LENGTH)
    needed_families: list[UUID]
    needed_supplies: list[str]
    status: str
    version: str | None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_method` tool on the given MCP server."""

    @mcp.tool(
        name="get_method",
        description="Read the current state of an existing method by id.",
    )
    async def get_method_tool(  # pyright: ignore[reportUnusedFunction]
        method_id: Annotated[
            UUID,
            Field(description="Target method's id."),
        ],
    ) -> MethodOutput:
        handler = get_handler()
        method = await handler(
            GetMethod(method_id=method_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if method is None:
            msg = f"Method {method_id} not found"
            raise ValueError(msg)
        return MethodOutput(
            id=method.id,
            name=method.name.value,
            needed_families=sorted(method.needed_families, key=str),
            needed_supplies=sorted(method.needed_supplies),
            status=method.status.value,
            version=method.version,
        )
