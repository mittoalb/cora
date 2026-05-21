"""MCP tool for the `register_actor` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool an MCP-aware client (e.g. Claude) can call.

Tool registration happens at app construction. The handler is fetched
at tool-call time via the `get_handler` callable so it sees the
lifespan-wired bundle on `app.state.access`. FastMCP derives the input
JSON schema from the function signature (one Annotated parameter per
field) and serializes the Pydantic return value as structured content
per the MCP 2025-06 spec update.
"""

from collections.abc import Callable
from typing import Annotated, Any, Literal
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.access.aggregates.actor import ACTOR_NAME_MAX_LENGTH, ActorKind
from cora.access.features.register_actor.command import RegisterActor
from cora.access.features.register_actor.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RegisterActorOutput(BaseModel):
    """Structured output of the `register_actor` MCP tool."""

    actor_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_actor` tool on the given MCP server.

    `get_handler` is invoked per-call (not at registration) so it sees
    the lifespan-wired bundle on `app.state.access.register_actor`.
    Domain / application errors raised by the handler propagate to
    FastMCP, which wraps them as structured `isError: true` responses.

    MCP tool calls don't currently support idempotency keys (no MCP
    standard for client-supplied retry tags); the wrapped handler is
    invoked with idempotency_key=None.
    """

    @mcp.tool(
        name="register_actor",
        description="Register a new actor with the given display name.",
    )
    async def register_actor_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=ACTOR_NAME_MAX_LENGTH,
                description="Display name for the new actor.",
            ),
        ],
        kind: Annotated[
            Literal["human", "service_account"],
            Field(
                description=(
                    "Closed discriminator. 'human' (default) for operator "
                    "registration. 'service_account' for machine callers. "
                    "'agent'-kind Actors are minted via define_agent only."
                ),
            ),
        ] = "human",
    ) -> RegisterActorOutput:
        handler = get_handler()
        actor_id = await handler(
            RegisterActor(name=name, kind=ActorKind(kind)),
            principal_id=get_mcp_principal_id(ctx),
            # MCP tools run inside the FastAPI-instrumented `/mcp`
            # request, so the OTel context is already in scope here.
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterActorOutput(actor_id=actor_id)
