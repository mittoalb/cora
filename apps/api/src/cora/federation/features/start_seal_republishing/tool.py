"""MCP tool for the `start_seal_republishing` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. Returns the facility_code back so the caller
can chain follow-up tools (complete_seal_republishing /
get_seal).
"""

from collections.abc import Callable
from typing import Annotated, Any

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.features.start_seal_republishing.command import (
    StartSealRepublishing,
)
from cora.federation.features.start_seal_republishing.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class StartSealRepublishingOutput(BaseModel):
    """Structured output of the `start_seal_republishing` MCP tool."""

    facility_code: str


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `start_seal_republishing` tool on the given MCP server."""

    @mcp.tool(
        name="start_seal_republishing",
        description=(
            "Start a republishing window on the Live Seal (Live -> "
            "Republishing). Single-source: requires the Seal to be in "
            "'Live' status. The online key continues to sign pointers "
            "during the window; consumers may use the Republishing "
            "indicator to defer trust on new pointers until "
            "complete_seal_republishing returns the singleton to Live. "
            "Strict-not-idempotent: starting against an already "
            "Republishing Seal raises."
        ),
    )
    async def start_seal_republishing_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        facility_code: Annotated[
            str,
            Field(min_length=1, description="Target Seal's facility code."),
        ],
        reason: Annotated[
            str | None,
            Field(
                description=(
                    "Optional operator note explaining why republishing "
                    "was started. Not persisted on the aggregate event "
                    "today; reserved for future audit overlays."
                ),
            ),
        ] = None,
    ) -> StartSealRepublishingOutput:
        handler = get_handler()
        await handler(
            StartSealRepublishing(
                facility_code=facility_code,
                reason=reason,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return StartSealRepublishingOutput(facility_code=facility_code)
