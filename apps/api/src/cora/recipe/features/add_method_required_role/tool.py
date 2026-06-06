"""MCP tool for `add_method_required_role`."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe._role_requirement_body import RoleRequirementBody
from cora.recipe.features.add_method_required_role.command import AddMethodRequiredRole
from cora.recipe.features.add_method_required_role.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `add_method_required_role` tool on the given MCP server."""

    @mcp.tool(
        name="add_method_required_role",
        description=(
            "Declare a positional role slot on an existing Method "
            "(positional role-tagging workstream; IEC 81346 Function "
            "aspect). The role carries a Method-local name, the Family "
            "the bound Asset must satisfy, a set of required ports, "
            "and an optional flag. Strict-not-idempotent on role_name; "
            "rejects when the method is Versioned or Deprecated. "
            "Plan-side binding lives in `bind_plan_role`."
        ),
    )
    async def add_method_required_role_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        method_id: Annotated[
            UUID,
            Field(description="Target method's id."),
        ],
        requirement: Annotated[
            RoleRequirementBody,
            Field(description="The positional role slot to declare."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            AddMethodRequiredRole(
                method_id=method_id,
                requirement=requirement.to_domain(),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
