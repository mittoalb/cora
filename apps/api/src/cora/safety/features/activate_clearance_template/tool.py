"""MCP tool for the `activate_clearance_template` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.safety.features.activate_clearance_template.command import (
    ActivateClearanceTemplate,
)
from cora.safety.features.activate_clearance_template.handler import Handler


class ActivateClearanceTemplateOutput(BaseModel):
    """Structured output of the `activate_clearance_template` MCP tool."""

    template_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `activate_clearance_template` tool on the given MCP server."""

    @mcp.tool(
        name="activate_clearance_template",
        description=(
            "Activate a Draft clearance template (Draft -> Active). The "
            "template becomes bindable via the `template_id` parameter on "
            "new clearance proposals. Requires template to be in 'Draft' status."
        ),
    )
    async def activate_clearance_template_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        template_id: Annotated[UUID, Field(description="Target template's id.")],
    ) -> ActivateClearanceTemplateOutput:
        handler = get_handler()
        await handler(
            ActivateClearanceTemplate(template_id=template_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return ActivateClearanceTemplateOutput(template_id=template_id)
