"""MCP tool for the `remove_subject` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.subject.features.remove_subject.command import RemoveSubject
from cora.subject.features.remove_subject.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `remove_subject` tool on the given MCP server."""

    @mcp.tool(
        name="remove_subject",
        description="Remove an existing subject from the apparatus.",
    )
    async def remove_subject_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        subject_id: Annotated[
            UUID,
            Field(description="Target subject's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            RemoveSubject(subject_id=subject_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
