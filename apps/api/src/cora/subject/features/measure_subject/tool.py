"""MCP tool for the `measure_subject` slice.

Mirror of `mount_subject` MCP tool. Single subject_id argument, no
structured content on success. Domain / application errors propagate
to FastMCP, which wraps them as `isError: true`.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.subject.features.measure_subject.command import MeasureSubject
from cora.subject.features.measure_subject.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `measure_subject` tool on the given MCP server."""

    @mcp.tool(
        name="measure_subject",
        description="Record a measurement on an existing subject.",
    )
    async def measure_subject_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        subject_id: Annotated[
            UUID,
            Field(description="Target subject's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            MeasureSubject(subject_id=subject_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
