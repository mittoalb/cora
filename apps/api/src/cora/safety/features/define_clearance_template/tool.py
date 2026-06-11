"""MCP tool for the `define_clearance_template` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool.
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
    CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH,
)
from cora.safety.features.define_clearance_template.command import (
    DefineClearanceTemplate,
)
from cora.safety.features.define_clearance_template.handler import IdempotentHandler


class DefineClearanceTemplateOutput(BaseModel):
    """Structured output of the `define_clearance_template` MCP tool."""

    template_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_clearance_template` tool on the given MCP server."""

    @mcp.tool(
        name="define_clearance_template",
        description="Define a new safety clearance template with the given code and title.",
    )
    async def define_clearance_template_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        code: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CLEARANCE_TEMPLATE_CODE_MAX_LENGTH,
                description=(
                    "Machine-readable code for the template "
                    "(facility-scoped; 1-50 chars after trim, e.g. 'ESAF', 'SAF')."
                ),
            ),
        ],
        title: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH,
                description="Display name for the new ClearanceTemplate.",
            ),
        ],
        facility_code: Annotated[
            str,
            Field(
                pattern=r"^[a-z0-9-]{1,32}$",
                description=(
                    "Facility code (cross-deployment convergent slug) this template belongs to."
                ),
            ),
        ],
        external_ref: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional external reference (e.g., upstream document identifier).",
            ),
        ] = None,
    ) -> DefineClearanceTemplateOutput:
        handler = get_handler()
        template_id = await handler(
            DefineClearanceTemplate(
                code=code,
                title=title,
                facility_code=facility_code,
                external_ref=external_ref,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DefineClearanceTemplateOutput(template_id=template_id)
