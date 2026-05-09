"""MCP tool for the `get_actor` query slice.

Surfaces the same handler the REST route uses. Returns a structured
ActorOutput on hit. On miss raises an exception that FastMCP wraps as
`isError: true` with a text diagnostic — matches the REST 404 behaviour
in MCP's error idiom (LLM consumers get a clear "actor not found"
message rather than null structuredContent they have to interpret).
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID, uuid4

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.access._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.access.aggregates.actor import ACTOR_NAME_MAX_LENGTH
from cora.access.features.get_actor.handler import Handler
from cora.access.features.get_actor.query import GetActor


class ActorOutput(BaseModel):
    """Structured output of the `get_actor` MCP tool."""

    id: UUID
    name: str = Field(..., max_length=ACTOR_NAME_MAX_LENGTH)
    is_active: bool


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_actor` tool on the given MCP server."""

    @mcp.tool(
        name="get_actor",
        description="Read the current state of an existing actor by id.",
    )
    async def get_actor_tool(  # pyright: ignore[reportUnusedFunction]
        actor_id: Annotated[
            UUID,
            Field(description="Target actor's id."),
        ],
    ) -> ActorOutput:
        handler = get_handler()
        actor = await handler(
            GetActor(actor_id=actor_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=uuid4(),
        )
        if actor is None:
            msg = f"Actor {actor_id} not found"
            raise ValueError(msg)
        return ActorOutput(
            id=actor.id,
            name=actor.name.value,
            is_active=actor.is_active,
        )
