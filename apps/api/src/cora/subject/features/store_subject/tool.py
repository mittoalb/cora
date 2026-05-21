"""MCP tool for the `store_subject` slice.

Mirror of the other terminal disposition MCP tools (return / discard).
Single subject_id argument, no structured content on success. Domain
/ application errors propagate to FastMCP, which wraps them as
`isError: true`.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.subject.features.store_subject.command import StoreSubject
from cora.subject.features.store_subject.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `store_subject` tool on the given MCP server."""

    @mcp.tool(
        name="store_subject",
        description="Archive an existing (Removed) subject on-site.",
    )
    async def store_subject_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        subject_id: Annotated[
            UUID,
            Field(description="Target subject's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            StoreSubject(subject_id=subject_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
