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
from typing import Annotated
from uuid import UUID, uuid4

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.access.aggregates.actor import ACTOR_NAME_MAX_LENGTH
from cora.access.features.register_actor.command import RegisterActor
from cora.access.features.register_actor.handler import Handler

# Phase 1 bootstrap: same as the REST route. Phase 3 swaps for the
# authenticated MCP caller surfaced through the Trust BC.
_SYSTEM_ACTOR_ID = UUID("00000000-0000-0000-0000-000000000000")


class RegisterActorOutput(BaseModel):
    """Structured output of the `register_actor` MCP tool."""

    actor_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `register_actor` tool on the given MCP server.

    `get_handler` is invoked per-call (not at registration) so it sees
    the lifespan-wired bundle on `app.state.access.register_actor`.
    Domain / application errors raised by the handler propagate to
    FastMCP, which wraps them as structured `isError: true` responses.
    """

    @mcp.tool(
        name="register_actor",
        description="Register a new actor with the given display name.",
    )
    async def register_actor_tool(  # pyright: ignore[reportUnusedFunction]
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=ACTOR_NAME_MAX_LENGTH,
                description="Display name for the new actor.",
            ),
        ],
    ) -> RegisterActorOutput:
        handler = get_handler()
        actor_id = await handler(
            RegisterActor(name=name),
            actor_id=_SYSTEM_ACTOR_ID,
            correlation_id=uuid4(),
        )
        return RegisterActorOutput(actor_id=actor_id)
