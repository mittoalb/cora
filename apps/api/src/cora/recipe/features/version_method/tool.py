"""MCP tool for the `version_method` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.aggregates.method import METHOD_VERSION_TAG_MAX_LENGTH
from cora.recipe.features.version_method.command import VersionMethod
from cora.recipe.features.version_method.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `version_method` tool on the given MCP server."""

    @mcp.tool(
        name="version_method",
        description=(
            "Issue a new version label for an existing method. Accepts "
            "both Defined and Versioned source states (subsequent "
            "revisions are allowed). Deprecated methods cannot be "
            "re-versioned."
        ),
    )
    async def version_method_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        method_id: Annotated[
            UUID,
            Field(description="Target method's id."),
        ],
        version_tag: Annotated[
            str,
            Field(
                min_length=1,
                max_length=METHOD_VERSION_TAG_MAX_LENGTH,
                description=(
                    "Operator-supplied label for this revision (for example 'v2', '2026-Q3')."
                ),
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            VersionMethod(method_id=method_id, version_tag=version_tag),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
