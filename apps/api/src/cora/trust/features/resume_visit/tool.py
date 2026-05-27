"""MCP tool for the `resume_visit` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.trust.features.resume_visit.command import ResumeVisit
from cora.trust.features.resume_visit.handler import Handler


class ResumeVisitOutput(BaseModel):
    """Structured output of the `resume_visit` MCP tool."""

    visit_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `resume_visit` tool on the given MCP server."""

    @mcp.tool(
        name="resume_visit",
        description=(
            "Resume an OnHold Visit (OnHold -> InProgress). The "
            "last_status_reason from the prior Hold is preserved across "
            "resume (audit breadcrumb)."
        ),
    )
    async def resume_visit_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        visit_id: Annotated[UUID, Field(description="Target Visit's id.")],
    ) -> ResumeVisitOutput:
        handler = get_handler()
        await handler(
            ResumeVisit(visit_id=visit_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ResumeVisitOutput(visit_id=visit_id)
