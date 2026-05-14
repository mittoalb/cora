"""MCP tool for the `dismount_subject` slice (Phase 4f)."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.infrastructure.observability import current_correlation_id
from cora.subject._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.subject.features.dismount_subject.command import DismountSubject
from cora.subject.features.dismount_subject.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `dismount_subject` tool on the given MCP server."""

    @mcp.tool(
        name="dismount_subject",
        description=(
            "Dismount a Subject from its current sample-environment "
            "Asset. Subject must be in `Mounted` or `Measured` "
            "state. Returns Subject to `Received` so it can be "
            "re-mounted (multi-stage workflow). Distinct from "
            "remove_subject which is terminal-leading."
        ),
    )
    async def dismount_subject_tool(  # pyright: ignore[reportUnusedFunction]
        subject_id: Annotated[
            UUID,
            Field(description="Target subject's id."),
        ],
        reason: Annotated[
            str,
            Field(
                min_length=1,
                max_length=500,
                description="Operator-supplied reason for the dismount (audit-log breadcrumb).",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            DismountSubject(subject_id=subject_id, reason=reason),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
