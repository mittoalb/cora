"""HTTP route for the `list_decisions` query slice.

`GET /decisions?cursor=...&confidence_band=Certain&decision_rule=auto-accept&actor_id=<uuid>`
returns `{"items": [...], "next_cursor": "..." | null}`.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel

from cora.decision.features.list_decisions.handler import Handler
from cora.decision.features.list_decisions.query import ConfidenceBandFilter, ListDecisions
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class DecisionSummaryDTO(BaseModel):
    """One decision in a paginated list."""

    decision_id: UUID
    actor_id: UUID
    decision_rule: str | None
    parent_id: UUID | None
    confidence: float | None
    confidence_band: ConfidenceBandFilter | None
    created_at: datetime


class DecisionListResponse(BaseModel):
    """Page of decisions plus opaque next-page cursor."""

    items: list[DecisionSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.decision.list_decisions
    return handler


router = APIRouter(tags=["decision"])


@router.get(
    "/decisions",
    status_code=status.HTTP_200_OK,
    response_model=DecisionListResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Query parameters failed validation OR `cursor` was "
                "malformed (corrupt base64, missing separator, bad "
                "timestamp / UUID)."
            ),
        },
    },
    summary="List decisions with cursor pagination + band/rule/actor filters",
)
async def list_decisions(
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    cursor: Annotated[
        str | None,
        Query(description="Opaque cursor from a previous page's `next_cursor`."),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Page size; capped at 100."),
    ] = 50,
    confidence_band: Annotated[
        ConfidenceBandFilter | None,
        Query(
            description=(
                "Optional confidence-band filter (Low / Medium / High / "
                "Certain). Decisions with no confidence are excluded "
                "when this filter is set."
            ),
        ),
    ] = None,
    decision_rule: Annotated[
        str | None,
        Query(description="Optional categorical decision-rule label filter."),
    ] = None,
    actor_id: Annotated[
        UUID | None,
        Query(description="Optional Actor-id filter."),
    ] = None,
) -> DecisionListResponse:
    page = await handler(
        ListDecisions(
            cursor=cursor,
            limit=limit,
            confidence_band=confidence_band,
            decision_rule=decision_rule,
            actor_id=actor_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return DecisionListResponse(
        items=[
            DecisionSummaryDTO(
                decision_id=item.decision_id,
                actor_id=item.actor_id,
                decision_rule=item.decision_rule,
                parent_id=item.parent_id,
                confidence=item.confidence,
                confidence_band=item.confidence_band,  # type: ignore[arg-type]
                created_at=item.created_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
