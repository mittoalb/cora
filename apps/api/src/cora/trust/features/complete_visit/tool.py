"""MCP tool for the `complete_visit` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.features.complete_visit.command import CompleteVisit
from cora.trust.features.complete_visit.handler import Handler


class CompleteVisitOutput(BaseModel):
    """Structured output of the `complete_visit` MCP tool."""

    visit_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `complete_visit` tool on the given MCP server."""

    @mcp.tool(
        name="complete_visit",
        description=(
            "Complete a Visit (InProgress | OnHold -> Completed). Normal "
            "terminal; no reason required."
        ),
    )
    async def complete_visit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        visit_id: Annotated[UUID, Field(description="Target Visit's id.")],
    ) -> CompleteVisitOutput:
        handler = get_handler()
        await handler(
            CompleteVisit(visit_id=visit_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return CompleteVisitOutput(visit_id=visit_id)
