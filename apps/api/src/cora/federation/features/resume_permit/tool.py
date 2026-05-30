"""MCP tool for the `resume_permit` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.features.resume_permit.command import ResumePermit
from cora.federation.features.resume_permit.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class ResumePermitOutput(BaseModel):
    """Structured output of the `resume_permit` MCP tool."""

    permit_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `resume_permit` tool on the given MCP server."""

    @mcp.tool(
        name="resume_permit",
        description=(
            "Resume a Suspended Permit back to Active (Suspended -> Active). "
            "Single-source: requires Permit to be in 'Suspended' status. For "
            "first-time activation from Defined, use 'activate_permit'."
        ),
    )
    async def resume_permit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        permit_id: Annotated[
            UUID,
            Field(description="Target permit's id."),
        ],
    ) -> ResumePermitOutput:
        handler = get_handler()
        await handler(
            ResumePermit(permit_id=permit_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ResumePermitOutput(permit_id=permit_id)
