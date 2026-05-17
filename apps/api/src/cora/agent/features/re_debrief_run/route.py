"""HTTP route for the `re_debrief_run` slice.

`POST /agents/run_debrief/invoke` with body `{run_id,
parent_decision_id?}`. Returns 201 + `{decision_id}` on success
(including the `DebriefDeferred` path, which still produces a
Decision -- operators distinguish via the `choice` field on the
returned Decision).

Idempotency-Key header (per Stripe / Adyen / PayPal convention)
makes the operator's retry safe: a second call with the same key
replays the cached `decision_id`.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from cora.agent.features.re_debrief_run.command import ReDebriefRun
from cora.agent.features.re_debrief_run.handler import IdempotentHandler
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


class ReDebriefRunRequest(BaseModel):
    """Body for `POST /agents/run_debrief/invoke`."""

    run_id: UUID = Field(
        ...,
        description="The Run to re-debrief. Must reference an existing Run.",
    )
    parent_decision_id: UUID | None = Field(
        default=None,
        description=(
            "Optional ref to the prior RunDebrief Decision being re-evaluated. "
            "When supplied, the new Decision's `parent_id` is set, forming a "
            "PROV-O `wasInformedBy` chain. Must reference the same Run as `run_id`."
        ),
    )


class ReDebriefRunResponse(BaseModel):
    """Response body for `POST /agents/run_debrief/invoke`."""

    decision_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler | None = request.app.state.agent.re_debrief_run
    if handler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "re_debrief_run is unavailable: kernel.llm is not wired "
                "(ANTHROPIC_API_KEY not configured). Configure the API key "
                "and restart, or use the test FakeLLMAdapter for non-prod."
            ),
        )
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/agents/run_debrief/invoke",
    status_code=status.HTTP_201_CREATED,
    response_model=ReDebriefRunResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Cross-aggregate invariant violated: Run missing, agent not "
                "seeded / deactivated, parent_decision missing, or parent "
                "Decision references a different Run."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation, OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ErrorResponse,
            "description": ("RunDebrief subscriber is not wired (ANTHROPIC_API_KEY unset)."),
        },
    },
    summary="Re-invoke RunDebrief on demand against a specific Run.",
)
async def post_re_debrief_run(
    body: ReDebriefRunRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReDebriefRunResponse:
    decision_id = await handler(
        ReDebriefRun(
            run_id=body.run_id,
            parent_decision_id=body.parent_decision_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        idempotency_key=idempotency_key,
    )
    return ReDebriefRunResponse(decision_id=decision_id)
