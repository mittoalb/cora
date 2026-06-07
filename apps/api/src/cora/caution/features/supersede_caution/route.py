"""HTTP route for the `supersede_caution` slice.

Action endpoint at `POST /cautions/{parent_id}/supersede`.
Body carries the child caution's full fields (target, category,
severity, text, workaround, authored_by, tags, expires_at,
propagate_to_children). Returns 201 + the new child's caution_id.

Reuses `register_caution`'s discriminated-union `TargetDTO` since
the child IS a registration. The parent id comes from the URL path.
The superseding-actor id comes from the request's authenticated
principal via the event envelope.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Request, status
from pydantic import BaseModel, Field

from cora.caution._caution_dtos import TargetDTO, target_from_dto
from cora.caution.aggregates.caution import (
    CAUTION_TEXT_MAX_LENGTH,
    CAUTION_WORKAROUND_MAX_LENGTH,
    CautionCategory,
    CautionSeverity,
)
from cora.caution.features.supersede_caution.command import SupersedeCaution
from cora.caution.features.supersede_caution.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class SupersedeCautionRequest(BaseModel):
    """Body for `POST /cautions/{parent_id}/supersede`.

    Mirrors `RegisterCautionRequest`'s child fields exactly. The
    `parent_id` comes from the URL path, not the body.
    """

    target: TargetDTO = Field(..., description="Must match parent's target.")
    category: CautionCategory
    severity: CautionSeverity
    text: str = Field(..., min_length=1, max_length=CAUTION_TEXT_MAX_LENGTH)
    workaround: str = Field(..., min_length=1, max_length=CAUTION_WORKAROUND_MAX_LENGTH)
    tags: list[str] = Field(default_factory=list)
    expires_at: datetime | None = Field(default=None)
    propagate_to_children: bool = Field(default=False)


class SupersedeCautionResponse(BaseModel):
    """Response body for `POST /cautions/{parent_id}/supersede`."""

    caution_id: UUID = Field(..., description="The new child caution's id.")


def _command_from_request(
    parent_id: UUID,
    body: SupersedeCautionRequest,
) -> SupersedeCaution:
    return SupersedeCaution(
        parent_id=parent_id,
        target=target_from_dto(body.target),
        category=body.category,
        severity=body.severity,
        text=body.text,
        workaround=body.workaround,
        tags=frozenset(body.tags),
        expires_at=body.expires_at,
        propagate_to_children=body.propagate_to_children,
    )


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.caution.supersede_caution
    return handler


router = APIRouter(tags=["caution"])


@router.post(
    "/cautions/{parent_id}/supersede",
    status_code=status.HTTP_201_CREATED,
    response_model=SupersedeCautionResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated on child fields (whitespace-only "
                "text/workaround/tag, past-dated expires_at, OR child target "
                "does not match parent's target)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No parent caution exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Parent is not in Active status (supersede_caution is single-"
                "source from Active only) OR optimistic-concurrency conflict "
                "on the parent stream (concurrent transition; retry)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation, OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Supersede an Active caution (atomic parent:Active->Superseded + child:Active)",
)
async def post_cautions_supersede(
    parent_id: Annotated[UUID, Path(description="Parent caution's id.")],
    body: SupersedeCautionRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied unique key per logical request. "
                "Retries with the same key + same body return the cached "
                "response instead of re-creating the child caution."
            ),
        ),
    ] = None,
) -> SupersedeCautionResponse:
    child_caution_id = await handler(
        _command_from_request(parent_id, body),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return SupersedeCautionResponse(caution_id=child_caution_id)
