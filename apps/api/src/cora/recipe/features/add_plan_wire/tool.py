"""MCP tool for the `add_plan_wire` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.aggregates.plan import WIRE_PORT_NAME_MAX_LENGTH
from cora.recipe.features.add_plan_wire.command import AddPlanWire
from cora.recipe.features.add_plan_wire.handler import Handler


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `add_plan_wire` tool on the given MCP server."""

    @mcp.tool(
        name="add_plan_wire",
        description=(
            "Add a typed port-to-port Wire to a Plan's wire set. "
            "The Wire connects an OUTPUT port on one bound Asset to "
            "an INPUT port on another (or the same) bound Asset, "
            "with matching signal_type. Fan-out is allowed (one "
            "source port can drive many target ports); fan-in is "
            "forbidden (each target port can be the destination of "
            "at most one Wire — use a Combiner Family Asset if "
            "you genuinely need multi-source aggregation). Strict-"
            "not-idempotent: re-adding the same wire raises "
            "PlanWireAlreadyExistsError."
        ),
    )
    async def add_plan_wire_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        plan_id: Annotated[UUID, Field(description="Target plan's id.")],
        source_asset_id: Annotated[
            UUID,
            Field(description="Asset whose OUTPUT port is the wire's source."),
        ],
        source_port_name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=WIRE_PORT_NAME_MAX_LENGTH,
                description="Source port name (must exist on the Asset, direction=OUTPUT).",
            ),
        ],
        target_asset_id: Annotated[
            UUID,
            Field(description="Asset whose INPUT port is the wire's target."),
        ],
        target_port_name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=WIRE_PORT_NAME_MAX_LENGTH,
                description="Target port name (must exist on the Asset, direction=INPUT).",
            ),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            AddPlanWire(
                plan_id=plan_id,
                source_asset_id=source_asset_id,
                source_port_name=source_port_name,
                target_asset_id=target_asset_id,
                target_port_name=target_port_name,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
