"""MCP tool for the `remove_plan_wire` slice (Phase 6h)."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.recipe.aggregates.plan import WIRE_PORT_NAME_MAX_LENGTH
from cora.recipe.features.remove_plan_wire.command import RemovePlanWire
from cora.recipe.features.remove_plan_wire.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `remove_plan_wire` tool on the given MCP server."""

    @mcp.tool(
        name="remove_plan_wire",
        description=(
            "Remove a typed port-to-port Wire from a Plan's wire "
            "set. Strict-not-idempotent: removing a wire that's not "
            "currently in the set raises PlanWireNotFoundError. The "
            "Wire's identity is the 4-tuple (source_asset_id, "
            "source_port_name, target_asset_id, target_port_name); "
            "all four must match exactly."
        ),
    )
    async def remove_plan_wire_tool(  # pyright: ignore[reportUnusedFunction]
        plan_id: Annotated[UUID, Field(description="Target plan's id.")],
        source_asset_id: Annotated[
            UUID,
            Field(description="The source-side Asset of the Wire to remove."),
        ],
        source_port_name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=WIRE_PORT_NAME_MAX_LENGTH,
                description="Source port name of the Wire to remove.",
            ),
        ],
        target_asset_id: Annotated[
            UUID,
            Field(description="The target-side Asset of the Wire to remove."),
        ],
        target_port_name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=WIRE_PORT_NAME_MAX_LENGTH,
                description="Target port name of the Wire to remove.",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            RemovePlanWire(
                plan_id=plan_id,
                source_asset_id=source_asset_id,
                source_port_name=source_port_name,
                target_asset_id=target_asset_id,
                target_port_name=target_port_name,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
