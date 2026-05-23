"""MCP tool for the `forget_actor` PII-erasure slice.

Surfaces the same handler the REST route uses. Tool registration
happens at app construction; the handler is fetched at tool-call
time via `get_handler` so it sees the lifespan-wired bundle.

NOTE: this tool gives MCP-shaped LLM clients a "forget user X"
verb. The v1 authz check is `AllowAllAuthorize` (same as every
other Access BC slice); when the GDPR-DPO authz widening lands
(per [[project_deferred]] trigger), this tool's exposure will be
gated on the appropriate Subject.kind.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from cora.access.features.forget_actor.command import ForgetActor
from cora.access.features.forget_actor.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `forget_actor` tool on the given MCP server."""

    @mcp.tool(
        name="forget_actor",
        description=(
            "Erase the actor_profile PII vault row for an existing actor "
            "(GDPR / PIPL / LGPD / CCPA right to be forgotten). The event "
            "log retains an audit record (no PII) of the erasure."
        ),
    )
    async def forget_actor_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        actor_id: Annotated[
            UUID,
            Field(description="Target actor's id."),
        ],
    ) -> None:
        handler = get_handler()
        await handler(
            ForgetActor(actor_id=actor_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
