"""MCP tool for the `remove_method_required_role` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.aggregates.method import ROLE_NAME_MAX_LENGTH, RoleName
from cora.recipe.features.remove_method_required_role.command import (
    RemoveMethodRequiredRole,
)
from cora.recipe.features.remove_method_required_role.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `remove_method_required_role` tool on the given MCP server."""

    @mcp.tool(
        name="remove_method_required_role",
        description=(
            "Remove a positional role slot from an existing Method. "
            "Strict-not-idempotent: an unknown role_name returns 404. "
            "Rejects when the method is Versioned or Deprecated."
        ),
    )
    async def remove_method_required_role_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        method_id: Annotated[
            UUID,
            Field(description="Target method's id."),
        ],
        role_name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=ROLE_NAME_MAX_LENGTH,
                description="The Method-local role label to remove.",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            RemoveMethodRequiredRole(
                method_id=method_id,
                role_name=RoleName(role_name),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
