"""HTTP route for the `list_policies` query slice.

`GET /policies?cursor=...&limit=50&conduit_id=...` returns
`{"items": [...], "next_cursor": "..." | null}`.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.trust.aggregates.policy import POLICY_NAME_MAX_LENGTH
from cora.trust.features.list_policies.handler import Handler
from cora.trust.features.list_policies.query import ListPolicies


class PolicySummaryDTO(BaseModel):
    """One policy in a paginated list."""

    policy_id: UUID
    name: str = Field(..., max_length=POLICY_NAME_MAX_LENGTH)
    conduit_id: UUID
    created_at: datetime


class PolicyListResponse(BaseModel):
    """Page of policies plus opaque next-page cursor."""

    items: list[PolicySummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.list_policies
    return handler


router = APIRouter(tags=["trust"])


@router.get(
    "/policies",
    status_code=status.HTTP_200_OK,
    response_model=PolicyListResponse,
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
    summary="List policies with cursor pagination + conduit filter",
)
async def list_policies(
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    cursor: Annotated[
        str | None,
        Query(description="Opaque cursor from a previous page's `next_cursor`."),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Page size; capped at 100."),
    ] = 50,
    conduit_id: Annotated[
        UUID | None,
        Query(description="Optional conduit-scope filter; omit for any conduit."),
    ] = None,
) -> PolicyListResponse:
    page = await handler(
        ListPolicies(cursor=cursor, limit=limit, conduit_id=conduit_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
    return PolicyListResponse(
        items=[
            PolicySummaryDTO(
                policy_id=item.policy_id,
                name=item.name,
                conduit_id=item.conduit_id,
                created_at=item.created_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
