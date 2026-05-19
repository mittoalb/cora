"""HTTP route for the `grant_tool_to_agent` slice.

Action endpoint at `POST /agents/{agent_id}/tools/grant`. Body
carries REQUIRED `tool_name` (1-100 chars after trim). 204 No
Content on success (including the idempotent re-grant case).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.agent.aggregates.agent import AGENT_TOOL_NAME_MAX_LENGTH
from cora.agent.features.grant_tool_to_agent.command import GrantToolToAgent
from cora.agent.features.grant_tool_to_agent.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class GrantToolToAgentRequest(BaseModel):
    """Body for `POST /agents/{agent_id}/tools/grant`."""

    tool_name: str = Field(
        min_length=1,
        max_length=AGENT_TOOL_NAME_MAX_LENGTH,
        description="MCP tool name to add to the Agent's allowlist (1-100 chars).",
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.agent.grant_tool_to_agent
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/agents/{agent_id}/tools/grant",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Tool name is empty / whitespace-only / over-cap, or grant "
                "would exceed the 32-entry cardinality cap."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No agent exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Agent is `Deprecated` (only blocking source state).",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body or path parameter failed schema validation.",
        },
    },
    summary="Grant one MCP tool to an Agent (idempotent re-grant emits no event)",
)
async def post_agents_grant_tool(
    agent_id: Annotated[UUID, Path(description="Target agent's id.")],
    body: GrantToolToAgentRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        GrantToolToAgent(agent_id=agent_id, tool_name=body.tool_name),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
