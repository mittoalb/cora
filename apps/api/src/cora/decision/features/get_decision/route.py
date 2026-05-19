"""HTTP route for the `get_decision` query slice."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.decision.aggregates.decision import (
    DECISION_CHOICE_MAX_LENGTH,
    DECISION_CONTEXT_MAX_LENGTH,
    confidence_band,
)
from cora.decision.features.get_decision.handler import Handler
from cora.decision.features.get_decision.query import GetDecision
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class DecisionResponse(BaseModel):
    """Read-side DTO at the API boundary.

    `confidence_band` is a derived field (Low / Medium / High /
    Certain) computed at read time from the stored `confidence`
    float. Never stored; one source of truth = the float.
    Returns null when confidence is null.
    """

    id: UUID
    actor_id: UUID
    context: str = Field(..., max_length=DECISION_CONTEXT_MAX_LENGTH)
    choice: str = Field(..., max_length=DECISION_CHOICE_MAX_LENGTH)
    parent_id: UUID | None
    override_kind: str | None
    decision_rule: str | None
    reasoning: str | None
    confidence: float | None
    confidence_source: str | None
    confidence_band: str | None
    alternatives: list[str]
    decision_inputs: dict[str, Any] | None
    reasoning_signature: str | None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.decision.get_decision
    return handler


router = APIRouter(tags=["decision"])


@router.get(
    "/decisions/{decision_id}",
    status_code=status.HTTP_200_OK,
    response_model=DecisionResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No decision exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a decision by id",
)
async def get_decisions(
    decision_id: Annotated[UUID, Path(description="Target decision's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> DecisionResponse:
    decision = await handler(
        GetDecision(decision_id=decision_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision {decision_id} not found",
        )
    band = confidence_band(decision.confidence)
    return DecisionResponse(
        id=decision.id,
        actor_id=decision.actor_id,
        context=decision.context.value,
        choice=decision.choice.value,
        parent_id=decision.parent_id,
        override_kind=decision.override_kind,
        decision_rule=decision.decision_rule.value if decision.decision_rule is not None else None,
        reasoning=decision.reasoning,
        confidence=decision.confidence,
        confidence_source=(
            decision.confidence_source.value if decision.confidence_source is not None else None
        ),
        confidence_band=band.value if band is not None else None,
        alternatives=list(decision.alternatives),
        decision_inputs=decision.decision_inputs,
        reasoning_signature=decision.reasoning_signature,
    )
