"""MCP tool for the `discard_subject` slice.

Mirror of the other terminal disposition MCP tools (return / store).
Subject_id + reason arguments, no structured content on success.
Domain / application errors propagate to FastMCP, which wraps them
as `isError: true`.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.infrastructure.observability import current_correlation_id
from cora.subject._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.subject.aggregates.subject import SUBJECT_DISCARD_REASON_MAX_LENGTH
from cora.subject.features.discard_subject.command import DiscardSubject
from cora.subject.features.discard_subject.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `discard_subject` tool on the given MCP server."""

    @mcp.tool(
        name="discard_subject",
        description=(
            "Destroy / discard an existing (Removed) subject. Re-discarding "
            "raises. Reason is free-form (1-500 chars), captured verbatim for "
            "GDPR + sample-handling audit."
        ),
    )
    async def discard_subject_tool(  # pyright: ignore[reportUnusedFunction]
        subject_id: Annotated[
            UUID,
            Field(description="Target subject's id."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=SUBJECT_DISCARD_REASON_MAX_LENGTH,
                description="Free-form reason for the discard (1-500 chars after trimming).",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DiscardSubject(subject_id=subject_id, reason=reason),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
