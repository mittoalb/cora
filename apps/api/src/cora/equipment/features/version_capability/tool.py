"""MCP tool for the `version_capability` slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.equipment._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.equipment.aggregates.capability import CAPABILITY_VERSION_TAG_MAX_LENGTH
from cora.equipment.features.version_capability.command import VersionCapability
from cora.equipment.features.version_capability.handler import Handler
from cora.infrastructure.observability import current_correlation_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `version_capability` tool on the given MCP server."""

    @mcp.tool(
        name="version_capability",
        description=(
            "Issue a new version label for an existing capability. "
            "Accepts both Defined and Versioned source states (subsequent "
            "revisions are allowed). Deprecated capabilities cannot be "
            "re-versioned."
        ),
    )
    async def version_capability_tool(  # pyright: ignore[reportUnusedFunction]
        capability_id: Annotated[
            UUID,
            Field(description="Target capability's id."),
        ],
        version_tag: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CAPABILITY_VERSION_TAG_MAX_LENGTH,
                description=(
                    "Operator-supplied label for this revision (for example 'v2', '2026-Q3')."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            VersionCapability(capability_id=capability_id, version_tag=version_tag),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
