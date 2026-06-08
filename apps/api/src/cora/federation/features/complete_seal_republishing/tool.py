"""MCP tool for the `complete_seal_republishing` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. Returns the facility_code back so the caller can
chain follow-up tools (sign_seal_pointer / rotate_seal_online_key /
get_seal).
"""

from collections.abc import Callable
from typing import Annotated, Any

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.features.complete_seal_republishing.command import (
    CompleteSealRepublishing,
)
from cora.federation.features.complete_seal_republishing.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class CompleteSealRepublishingOutput(BaseModel):
    """Structured output of the `complete_seal_republishing` MCP tool."""

    facility_code: str


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `complete_seal_republishing` tool on the given MCP server."""

    @mcp.tool(
        name="complete_seal_republishing",
        description=(
            "Complete an in-flight Seal republish (Republishing -> Live). "
            "Single-source: requires the Seal to be in 'Republishing' status. "
            "Optionally refreshes the head pointer when new_head_hash and "
            "new_sequence_number are supplied together (sequence must be "
            "strictly greater than the current value)."
        ),
    )
    async def complete_seal_republishing_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        facility_code: Annotated[
            str,
            Field(description="Target Seal's facility code."),
        ],
        new_head_hash: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "SHA-256 (lowercase hex) of the fresh head pointer. Must "
                    "be supplied together with new_sequence_number or "
                    "omitted together."
                ),
            ),
        ] = None,
        new_sequence_number: Annotated[
            int | None,
            Field(
                default=None,
                description=(
                    "Monotonic sequence for the fresh head pointer. Strictly "
                    "greater than the current value. Must be supplied "
                    "together with new_head_hash or omitted together."
                ),
            ),
        ] = None,
    ) -> CompleteSealRepublishingOutput:
        handler = get_handler()
        await handler(
            CompleteSealRepublishing(
                facility_code=facility_code,
                new_head_hash=new_head_hash,
                new_sequence_number=new_sequence_number,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return CompleteSealRepublishingOutput(facility_code=facility_code)
