"""MCP tool for the `decommission_facility` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. Mirrors `revoke_credential`'s tool surface.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.features.decommission_facility.command import DecommissionFacility
from cora.federation.features.decommission_facility.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class DecommissionFacilityOutput(BaseModel):
    """Structured output of the `decommission_facility` MCP tool."""

    facility_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `decommission_facility` tool on the given MCP server."""

    @mcp.tool(
        name="decommission_facility",
        description=(
            "Decommission a Facility (terminal: Active -> Decommissioned). "
            "Strict-not-idempotent: decommissioning an already-Decommissioned "
            "facility raises. The code stays reserved post-decommissioning "
            "(the projection UNIQUE INDEX on code covers Decommissioned rows "
            "too); re-registering with the same code is forbidden. To revive "
            "the operational role under a fresh identity, mint a new "
            "FacilityCode via register_facility."
        ),
    )
    async def decommission_facility_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        facility_id: Annotated[
            UUID,
            Field(description="Target facility's id."),
        ],
        reason: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Optional free-text operator intent for the decommission. "
                    "Flows onto the FacilityDecommissioned event payload."
                ),
            ),
        ] = None,
    ) -> DecommissionFacilityOutput:
        handler = get_handler()
        await handler(
            DecommissionFacility(facility_id=FacilityId(facility_id), reason=reason),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DecommissionFacilityOutput(facility_id=facility_id)
