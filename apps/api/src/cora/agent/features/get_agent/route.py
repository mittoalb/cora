"""HTTP route for the `get_agent` query slice.

`GET /agents/{agent_id}` returns 200 + AgentResponse on hit, 404
on miss. The handler returns `Agent | None`; the route maps None
to 404 via HTTPException.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel

from cora.agent.aggregates.agent import Agent, AgentStatus
from cora.agent.features.get_agent.handler import Handler
from cora.agent.features.get_agent.query import GetAgent
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class ModelRefResponse(BaseModel):
    """Sub-DTO for the typed ModelRef VO."""

    provider: str
    model: str
    snapshot_pin: str | None = None


class AgentResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. Decouples the wire format
    from the domain model so the two can evolve independently.
    """

    id: UUID
    kind: str
    name: str
    version: str
    model_ref: ModelRefResponse
    status: AgentStatus
    defined_at: datetime
    description: str | None = None
    canonical_uri: str | None = None
    prompt_template_id: UUID | None = None
    capabilities: list[str]
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None
    deprecation_reason: str | None = None


def _response_from_state(agent: Agent) -> AgentResponse:
    return AgentResponse(
        id=agent.id,
        kind=agent.kind.value,
        name=agent.name.value,
        version=agent.version.value,
        model_ref=ModelRefResponse(
            provider=agent.model_ref.provider,
            model=agent.model_ref.model,
            snapshot_pin=agent.model_ref.snapshot_pin,
        ),
        status=agent.status,
        defined_at=agent.defined_at,
        description=agent.description.value if agent.description is not None else None,
        canonical_uri=agent.canonical_uri.value if agent.canonical_uri is not None else None,
        prompt_template_id=agent.prompt_template_id,
        capabilities=sorted(c.value for c in agent.capabilities),
        versioned_at=agent.versioned_at,
        deprecated_at=agent.deprecated_at,
        deprecation_reason=(
            agent.deprecation_reason.value if agent.deprecation_reason is not None else None
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.agent.get_agent
    return handler


router = APIRouter(tags=["agent"])


@router.get(
    "/agents/{agent_id}",
    status_code=status.HTTP_200_OK,
    response_model=AgentResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No agent exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get an agent by id",
)
async def get_agents(
    agent_id: Annotated[UUID, Path(description="Target agent's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> AgentResponse:
    agent = await handler(
        GetAgent(agent_id=agent_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )
    return _response_from_state(agent)
