"""HTTP route for the `version_agent` slice.

Action endpoint at `POST /agents/{agent_id}/version`. Empty body.
204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.agent.features.version_agent.command import VersionAgent
from cora.agent.features.version_agent.handler import Handler
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.agent.version_agent
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/agents/{agent_id}/version",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
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
            "description": (
                "Agent is not in Defined status (version_agent is single-source from Defined only)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Version a Defined Agent (Defined -> Versioned)",
)
async def post_agents_version(
    agent_id: Annotated[UUID, Path(description="Target agent's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        VersionAgent(agent_id=agent_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
