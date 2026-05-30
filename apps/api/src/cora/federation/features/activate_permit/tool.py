"""MCP tool for the `activate_permit` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. Returns the permit_id back so the caller can
chain follow-up tools (suspend / revoke / get_permit).
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.features.activate_permit.command import ActivatePermit
from cora.federation.features.activate_permit.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class ActivatePermitOutput(BaseModel):
    """Structured output of the `activate_permit` MCP tool."""

    permit_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `activate_permit` tool on the given MCP server."""

    @mcp.tool(
        name="activate_permit",
        description=(
            "Activate a Defined permit (Defined -> Active). Single-source: "
            "requires the Permit to be in 'Defined' status. To re-activate "
            "from a Suspended state, use 'resume_permit'."
        ),
    )
    async def activate_permit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        permit_id: Annotated[
            UUID,
            Field(description="Target permit's id."),
        ],
    ) -> ActivatePermitOutput:
        handler = get_handler()
        await handler(
            ActivatePermit(permit_id=permit_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ActivatePermitOutput(permit_id=permit_id)
