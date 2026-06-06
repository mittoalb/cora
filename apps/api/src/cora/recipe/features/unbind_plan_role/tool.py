"""MCP tool for the `unbind_plan_role` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.aggregates.method import ROLE_NAME_MAX_LENGTH, RoleName
from cora.recipe.features.unbind_plan_role.command import UnbindPlanRole
from cora.recipe.features.unbind_plan_role.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `unbind_plan_role` tool on the given MCP server."""

    @mcp.tool(
        name="unbind_plan_role",
        description=(
            "Remove a RoleBinding from an existing Plan. Strict-not-"
            "idempotent: an unknown role_name returns 404. Rejects "
            "when the Plan is Versioned/Deprecated."
        ),
    )
    async def unbind_plan_role_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        plan_id: Annotated[
            UUID,
            Field(description="Target plan's id."),
        ],
        role_name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=ROLE_NAME_MAX_LENGTH,
                description="role_name whose binding to remove.",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            UnbindPlanRole(
                plan_id=plan_id,
                role_name=RoleName(role_name),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
