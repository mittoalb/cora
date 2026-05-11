"""MCP tool for the `get_practice` query slice.

Surfaces the same handler the REST route uses. Returns a structured
PracticeOutput on hit. On miss raises an exception that FastMCP
wraps as `isError: true` with a text diagnostic.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.aggregates.practice import PRACTICE_NAME_MAX_LENGTH
from cora.recipe.features.get_practice.handler import Handler
from cora.recipe.features.get_practice.query import GetPractice


class PracticeOutput(BaseModel):
    """Structured output of the `get_practice` MCP tool."""

    id: UUID
    name: str = Field(..., max_length=PRACTICE_NAME_MAX_LENGTH)
    method_id: UUID
    site_id: UUID
    status: str
    current_version: str | None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_practice` tool on the given MCP server."""

    @mcp.tool(
        name="get_practice",
        description="Read the current state of an existing practice by id.",
    )
    async def get_practice_tool(  # pyright: ignore[reportUnusedFunction]
        practice_id: Annotated[
            UUID,
            Field(description="Target practice's id."),
        ],
    ) -> PracticeOutput:
        handler = get_handler()
        practice = await handler(
            GetPractice(practice_id=practice_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        if practice is None:
            msg = f"Practice {practice_id} not found"
            raise ValueError(msg)
        return PracticeOutput(
            id=practice.id,
            name=practice.name.value,
            method_id=practice.method_id,
            site_id=practice.site_id,
            status=practice.status.value,
            current_version=practice.current_version,
        )
