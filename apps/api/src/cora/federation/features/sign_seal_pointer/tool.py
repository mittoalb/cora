"""MCP tool for the `sign_seal_pointer` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. Returns the facility_id and the new sequence
number back so the caller can chain follow-up tools
(get_seal / rotate_seal_online_key / start_seal_republishing).
"""

from collections.abc import Callable
from typing import Annotated, Any

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.features.sign_seal_pointer.command import SignSealPointer
from cora.federation.features.sign_seal_pointer.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class SignSealPointerOutput(BaseModel):
    """Structured output of the `sign_seal_pointer` MCP tool."""

    facility_id: str
    new_sequence_number: int


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `sign_seal_pointer` tool on the given MCP server."""

    @mcp.tool(
        name="sign_seal_pointer",
        description=(
            "Sign a new head pointer on a Live Seal (Live -> Live). "
            "Single-source: requires the Seal to be in 'Live' status. "
            "new_head_hash is the SHA-256 lowercase hex of the "
            "canonicalized head pointer body; new_sequence_number is the "
            "monotonic counter for the signed pointer chain and must "
            "strictly exceed the Seal's current_sequence_number. "
            "Strict-not-idempotent: signing from a non-Live posture "
            "raises, as does supplying a sequence number that does not "
            "strictly exceed the prior."
        ),
    )
    async def sign_seal_pointer_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        facility_id: Annotated[
            str,
            Field(min_length=1, description="Target facility's id."),
        ],
        new_head_hash: Annotated[
            str,
            Field(
                min_length=1,
                description=(
                    "SHA-256 lowercase hex of the canonicalized head "
                    "pointer body just signed by the online key."
                ),
            ),
        ],
        new_sequence_number: Annotated[
            int,
            Field(
                ge=1,
                description=(
                    "Monotonic counter for the signed pointer chain. "
                    "Must strictly exceed the Seal's "
                    "current_sequence_number."
                ),
            ),
        ],
    ) -> SignSealPointerOutput:
        handler = get_handler()
        await handler(
            SignSealPointer(
                facility_id=facility_id,
                new_head_hash=new_head_hash,
                new_sequence_number=new_sequence_number,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return SignSealPointerOutput(
            facility_id=facility_id,
            new_sequence_number=new_sequence_number,
        )
