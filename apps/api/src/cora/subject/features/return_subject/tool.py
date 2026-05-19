"""MCP tool for the `return_subject` slice.

Mirror of `measure_subject` / `remove_subject` MCP tools. Single
subject_id argument, no structured content on success. Domain /
application errors propagate to FastMCP, which wraps them as
`isError: true`.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.subject._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.subject.features.return_subject.command import ReturnSubject
from cora.subject.features.return_subject.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `return_subject` tool on the given MCP server."""

    @mcp.tool(
        name="return_subject",
        description="Return an existing (Removed) subject to its owner / submitter.",
    )
    async def return_subject_tool(  # pyright: ignore[reportUnusedFunction]
        subject_id: Annotated[
            UUID,
            Field(description="Target subject's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            ReturnSubject(subject_id=subject_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
