"""MCP tool for the `version_practice` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.infrastructure.observability import current_correlation_id
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.aggregates.practice import PRACTICE_VERSION_TAG_MAX_LENGTH
from cora.recipe.features.version_practice.command import VersionPractice
from cora.recipe.features.version_practice.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `version_practice` tool on the given MCP server."""

    @mcp.tool(
        name="version_practice",
        description=(
            "Issue a new version label for an existing practice. "
            "Accepts both Defined and Versioned source states "
            "(subsequent revisions allowed). Deprecated practices "
            "cannot be re-versioned."
        ),
    )
    async def version_practice_tool(  # pyright: ignore[reportUnusedFunction]
        practice_id: Annotated[
            UUID,
            Field(description="Target practice's id."),
        ],
        version_tag: Annotated[
            str,
            Field(
                min_length=1,
                max_length=PRACTICE_VERSION_TAG_MAX_LENGTH,
                description=(
                    "Operator-supplied label for this revision (for example 'v2', '2026-Q3')."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            VersionPractice(practice_id=practice_id, version_tag=version_tag),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
