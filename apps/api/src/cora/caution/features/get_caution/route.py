"""HTTP route for the `get_caution` query slice.

`GET /cautions/{caution_id}` returns 200 + CautionResponse on hit,
404 on miss. The handler returns `Caution | None`; the route maps
None to 404 via HTTPException (idiomatic in routes; the BC's
exception-handler infrastructure stays focused on domain /
application errors raised deeper in the stack).
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.caution.aggregates.caution import (
    Caution,
    CautionCategory,
    CautionRetireReason,
    CautionSeverity,
    CautionStatus,
    serialize_target,
)
from cora.caution.features.get_caution.handler import Handler
from cora.caution.features.get_caution.query import GetCaution
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class CautionResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. Decouples the wire format
    from the domain model so the two can evolve independently.
    `target` is rendered via the public `serialize_target` helper as
    `{kind, id}`.
    """

    id: UUID
    target: dict[str, Any] = Field(
        ..., description="Discriminated target: {kind: 'Asset'|'Procedure', id: <uuid>}"
    )
    category: CautionCategory
    severity: CautionSeverity
    text: str
    workaround: str
    author_actor_id: UUID
    tags: list[str]
    expires_at: datetime | None
    propagate_to_children: bool
    status: CautionStatus
    parent_id: UUID | None = None
    superseded_by_caution_id: UUID | None = None
    retired_reason: CautionRetireReason | None = None


def _response_from_state(caution: Caution) -> CautionResponse:
    return CautionResponse(
        id=caution.id,
        target=serialize_target(caution.target),
        category=caution.category,
        severity=caution.severity,
        text=caution.text.value,
        workaround=caution.workaround.value,
        author_actor_id=caution.author_actor_id,
        tags=sorted(t.value for t in caution.tags),
        expires_at=caution.expires_at,
        propagate_to_children=caution.propagate_to_children,
        status=caution.status,
        parent_id=caution.parent_id,
        superseded_by_caution_id=caution.superseded_by_caution_id,
        retired_reason=caution.retired_reason,
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.caution.get_caution
    return handler


router = APIRouter(tags=["caution"])


@router.get(
    "/cautions/{caution_id}",
    status_code=status.HTTP_200_OK,
    response_model=CautionResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No caution exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a caution by id",
)
async def get_cautions(
    caution_id: Annotated[UUID, Path(description="Target caution's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> CautionResponse:
    caution = await handler(
        GetCaution(caution_id=caution_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if caution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Caution {caution_id} not found",
        )
    return _response_from_state(caution)
