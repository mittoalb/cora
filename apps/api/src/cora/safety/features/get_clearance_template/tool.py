"""MCP tool for the `get_clearance_template` query slice.

Surfaces the same handler the REST route uses. Returns a structured
ClearanceTemplateOutput on hit. On miss raises an exception that
FastMCP wraps as `isError: true` with a text diagnostic  --  matches
the REST 404 behaviour in MCP's error idiom (LLM consumers get a
clear "clearance template not found" message rather than null
structuredContent they have to interpret).
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.safety.aggregates.clearance_template import (
    CLEARANCE_TEMPLATE_CODE_MAX_LENGTH,
    CLEARANCE_TEMPLATE_EXTERNAL_REF_MAX_LENGTH,
    CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH,
    ClearanceTemplateNotFoundError,
)
from cora.safety.features.get_clearance_template.handler import Handler
from cora.safety.features.get_clearance_template.query import GetClearanceTemplate


class ClearanceTemplateOutput(BaseModel):
    """Structured output of the `get_clearance_template` MCP tool."""

    id: UUID
    code: str = Field(..., max_length=CLEARANCE_TEMPLATE_CODE_MAX_LENGTH)
    title: str = Field(..., max_length=CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH)
    facility_code: str
    version: int
    supersedes_template_id: UUID | None
    external_ref: str | None = Field(
        default=None, max_length=CLEARANCE_TEMPLATE_EXTERNAL_REF_MAX_LENGTH
    )
    status: str
    defined_at: str
    defined_by: str


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_clearance_template` tool on the given MCP server."""

    @mcp.tool(
        name="get_clearance_template",
        description="Read the current state of an existing clearance template by id.",
    )
    async def get_clearance_template_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        template_id: Annotated[
            UUID,
            Field(description="Target clearance template's id."),
        ],
    ) -> ClearanceTemplateOutput:
        handler = get_handler()
        template = await handler(
            GetClearanceTemplate(template_id=template_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if template is None:
            raise ClearanceTemplateNotFoundError(template_id)
        return ClearanceTemplateOutput(
            id=template.id,
            code=template.code.value,
            title=template.title.value,
            facility_code=template.facility_code.value,
            version=template.version.value,
            supersedes_template_id=template.supersedes_template_id,
            external_ref=template.external_ref,
            status=template.status.value,
            defined_at=template.defined_at.isoformat(),
            defined_by=str(template.defined_by),
        )
