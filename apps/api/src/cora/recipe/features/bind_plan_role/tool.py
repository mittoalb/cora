"""MCP tool for `bind_plan_role`."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.aggregates.method import ROLE_NAME_MAX_LENGTH, RoleName
from cora.recipe.features.bind_plan_role.command import BindPlanRole
from cora.recipe.features.bind_plan_role.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `bind_plan_role` tool on the given MCP server."""

    @mcp.tool(
        name="bind_plan_role",
        description=(
            "Bind a Method.required_role to a specific Asset on an "
            "existing Plan (positional role-tagging; IEC 81346 Function "
            "aspect). The binding is validated against the Method's "
            "required_roles + the Asset's family_ids + the Asset's "
            "ports + the existing wire graph. Strict-not-idempotent on "
            "role_name; rejects when the Plan is Versioned/Deprecated."
        ),
    )
    async def bind_plan_role_tool(  # pyright: ignore[reportUnusedFunction]
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
                description="Method-local role label to bind.",
            ),
        ],
        asset_id: Annotated[
            UUID,
            Field(description="Asset filling the role."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            BindPlanRole(
                plan_id=plan_id,
                role_name=RoleName(role_name),
                asset_id=asset_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
