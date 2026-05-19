"""MCP tool for the `remove_subject` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.subject._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.subject.features.remove_subject.command import RemoveSubject
from cora.subject.features.remove_subject.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `remove_subject` tool on the given MCP server."""

    @mcp.tool(
        name="remove_subject",
        description="Remove an existing subject from the apparatus.",
    )
    async def remove_subject_tool(  # pyright: ignore[reportUnusedFunction]
        subject_id: Annotated[
            UUID,
            Field(description="Target subject's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            RemoveSubject(subject_id=subject_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
