"""HTTP route for the `resume_agent` slice.

Action endpoint at `POST /agents/{agent_id}/resume`. No request
body (resume has no reason field; asymmetry with `suspend_agent`
is deliberate). 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.agent.features.resume_agent.command import ResumeAgent
from cora.agent.features.resume_agent.handler import Handler
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.agent.resume_agent
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/agents/{agent_id}/resume",
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
                "Agent is not in `Suspended` (strict-not-idempotent: only a "
                "`Suspended` agent can be resumed)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Resume an Agent (Suspended -> Versioned; non-terminal)",
)
async def post_agents_resume(
    agent_id: Annotated[UUID, Path(description="Target agent's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        ResumeAgent(agent_id=agent_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
