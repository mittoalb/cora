"""MCP tool for the `rotate_seal_online_key` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. Mirrors `revoke_credential`'s tool surface: a
security-touching mid-lifecycle transition whose audit emission is
atomic with the domain event.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.features.rotate_seal_online_key.command import (
    RotateSealOnlineKey,
)
from cora.federation.features.rotate_seal_online_key.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RotateSealOnlineKeyOutput(BaseModel):
    """Structured output of the `rotate_seal_online_key` MCP tool."""

    facility_id: str
    new_online_key_ref: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `rotate_seal_online_key` tool on the given MCP server."""

    @mcp.tool(
        name="rotate_seal_online_key",
        description=(
            "Rotate the Seal singleton's online (warm) signing key to a "
            "fresh Credential. Requires the Seal to be Live; rejects "
            "Republishing. Rejects rotations to the current online ref "
            "(no-op) and to a ref equal to the offline ref (key-separation "
            "invariant). Emits a paired Decision-BC audit atomically."
        ),
    )
    async def rotate_seal_online_key_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        facility_id: Annotated[
            str,
            Field(description="Target Seal's facility id."),
        ],
        new_online_key_ref: Annotated[
            UUID,
            Field(
                description=(
                    "Credential id of the fresh online (warm) signing key. "
                    "Must differ from both the current online_key_ref and "
                    "the current offline_key_ref."
                ),
            ),
        ],
    ) -> RotateSealOnlineKeyOutput:
        handler = get_handler()
        await handler(
            RotateSealOnlineKey(
                facility_id=facility_id,
                new_online_key_ref=new_online_key_ref,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RotateSealOnlineKeyOutput(
            facility_id=facility_id,
            new_online_key_ref=new_online_key_ref,
        )
