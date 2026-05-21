"""MCP tool for the `get_subject` query slice.

Surfaces the same handler the REST route uses. Returns a structured
SubjectOutput on hit. On miss raises an exception that FastMCP wraps
as `isError: true` with a text diagnostic — matches the REST 404
behaviour in MCP's error idiom (LLM consumers get a clear "subject
not found" message rather than null structuredContent they have to
interpret).
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.subject.aggregates.subject import SUBJECT_NAME_MAX_LENGTH
from cora.subject.features.get_subject.handler import Handler
from cora.subject.features.get_subject.query import GetSubject


class SubjectOutput(BaseModel):
    """Structured output of the `get_subject` MCP tool."""

    id: UUID
    name: str = Field(..., max_length=SUBJECT_NAME_MAX_LENGTH)
    status: str
    mounted_on_asset_id: UUID | None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_subject` tool on the given MCP server."""

    @mcp.tool(
        name="get_subject",
        description="Read the current state of an existing subject by id.",
    )
    async def get_subject_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        subject_id: Annotated[
            UUID,
            Field(description="Target subject's id."),
        ],
    ) -> SubjectOutput:
        handler = get_handler()
        subject = await handler(
            GetSubject(subject_id=subject_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if subject is None:
            msg = f"Subject {subject_id} not found"
            raise ValueError(msg)
        return SubjectOutput(
            id=subject.id,
            name=subject.name.value,
            status=subject.status.value,
            mounted_on_asset_id=subject.mounted_on_asset_id,
        )
