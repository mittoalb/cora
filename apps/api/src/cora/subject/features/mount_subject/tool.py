"""MCP tool for the `mount_subject` slice.

Surfaces the same handler the REST route uses. Subject_id + asset_id
arguments, no structured content (None on success). Domain /
application errors raised by the handler propagate to FastMCP, which
wraps them as `isError: true` responses.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.infrastructure.observability import current_correlation_id
from cora.subject._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.subject.features.mount_subject.command import MountSubject
from cora.subject.features.mount_subject.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `mount_subject` tool on the given MCP server."""

    @mcp.tool(
        name="mount_subject",
        description=(
            "Mount an existing subject onto a sample-environment Asset. "
            "Subject must be in `Received` state; Asset must be `Active`."
        ),
    )
    async def mount_subject_tool(  # pyright: ignore[reportUnusedFunction]
        subject_id: Annotated[
            UUID,
            Field(description="Target subject's id."),
        ],
        asset_id: Annotated[
            UUID,
            Field(description="Sample-environment Asset id (must be Active)."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=500,
                description="Operator-supplied reason for the mount (audit-log breadcrumb).",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            MountSubject(subject_id=subject_id, asset_id=asset_id, reason=reason),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
