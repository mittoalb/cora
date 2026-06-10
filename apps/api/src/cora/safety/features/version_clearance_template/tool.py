"""MCP tool for the `version_clearance_template` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.safety.features.version_clearance_template.command import (
    VersionClearanceTemplate,
)
from cora.safety.features.version_clearance_template.handler import Handler


class VersionClearanceTemplateOutput(BaseModel):
    """Structured output of the `version_clearance_template` MCP tool."""

    template_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `version_clearance_template` tool on the given MCP server."""

    @mcp.tool(
        name="version_clearance_template",
        description=(
            "Record a new version of an Active ClearanceTemplate. Additive "
            "within Active (no FSM transition); the parent template must be "
            "in the same facility and new_version must equal current_version + 1."
        ),
    )
    async def version_clearance_template_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        template_id: Annotated[UUID, Field(description="Target template's id.")],
        new_version: Annotated[
            int,
            Field(
                ge=2,
                description="Monotonic version number; must equal current_version + 1.",
            ),
        ],
        supersedes_template_id: Annotated[
            UUID,
            Field(description="Parent template id; must be in the same facility."),
        ],
    ) -> VersionClearanceTemplateOutput:
        handler = get_handler()
        await handler(
            VersionClearanceTemplate(
                template_id=template_id,
                new_version=new_version,
                supersedes_template_id=supersedes_template_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return VersionClearanceTemplateOutput(template_id=template_id)
