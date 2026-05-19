"""HTTP route for the `define_practice` slice.

Pydantic request/response schemas + APIRouter for `POST /practices`.
The slice's BC-level wiring (`cora.recipe.routes.register_recipe_routes`)
includes this router on the FastAPI app.

`method_id` and `site_id` are required UUIDs. Eventual-consistency:
neither is verified against the corresponding aggregate stream;
mismatch surfaces at Plan binding (6e).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.recipe.aggregates.practice import PRACTICE_NAME_MAX_LENGTH
from cora.recipe.features.define_practice.command import DefinePractice
from cora.recipe.features.define_practice.handler import IdempotentHandler


class DefinePracticeRequest(BaseModel):
    """Body for `POST /practices`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=PRACTICE_NAME_MAX_LENGTH,
        description="Display name for the new practice.",
    )
    method_id: UUID = Field(
        ...,
        description=(
            "Method id this Practice adapts. Eventual-consistency: "
            "existence is NOT verified against the Method stream at "
            "decide time; mismatch surfaces at Plan binding (Phase 6e)."
        ),
    )
    site_id: UUID = Field(
        ...,
        description=(
            "Site-level Asset id this Practice belongs to "
            "(institutional ownership). Eventual-consistency: "
            "existence and level are NOT verified at decide time."
        ),
    )


class DefinePracticeResponse(BaseModel):
    """Response body for `POST /practices`."""

    practice_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.recipe.define_practice
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/practices",
    status_code=status.HTTP_201_CREATED,
    response_model=DefinePracticeResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (whitespace-only name).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Define a new facility-adapted Method (Practice)",
)
async def post_practices(
    body: DefinePracticeRequest,
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
                "response instead of re-creating the practice."
            ),
        ),
    ] = None,
) -> DefinePracticeResponse:
    practice_id = await handler(
        DefinePractice(
            name=body.name,
            method_id=body.method_id,
            site_id=body.site_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return DefinePracticeResponse(practice_id=practice_id)
