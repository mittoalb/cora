"""HTTP route for the `get_practice` query slice.

`GET /practices/{practice_id}` returns 200 + PracticeResponse on
hit, 404 on miss. The handler returns `PracticeView | None`; the
route maps None to 404 via HTTPException.

`created_at` / `versioned_at` / `deprecated_at` are sourced from the
`proj_recipe_practice_summary` projection, not from aggregate state
(Path C). Null semantics under eventual
consistency: read together with `status`. A 200 with a populated
`status` but null timestamp means projection lag, never a missing
transition. A 404 means the Practice aggregate itself does not exist.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.recipe.aggregates.practice import PRACTICE_NAME_MAX_LENGTH
from cora.recipe.features.get_practice.handler import Handler
from cora.recipe.features.get_practice.query import GetPractice


class PracticeResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. `status` is the StrEnum's
    string value (Defined / Versioned / Deprecated). `version` is the
    operator-supplied label of the most recent version_practice call
    (null until first version). `created_at` / `versioned_at` /
    `deprecated_at` are projection-sourced lifecycle timestamps
    (Path C); see module docstring for
    null-semantics.
    """

    id: UUID
    name: str = Field(..., max_length=PRACTICE_NAME_MAX_LENGTH)
    method_id: UUID
    site_id: UUID
    status: str
    version: str | None
    created_at: datetime | None = None
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.get_practice
    return handler


router = APIRouter(tags=["recipe"])


@router.get(
    "/practices/{practice_id}",
    status_code=status.HTTP_200_OK,
    response_model=PracticeResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No practice exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a practice by id",
)
async def get_practices(
    practice_id: Annotated[UUID, Path(description="Target practice's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> PracticeResponse:
    view = await handler(
        GetPractice(practice_id=practice_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Practice {practice_id} not found",
        )
    practice = view.practice
    timestamps = view.timestamps
    return PracticeResponse(
        id=practice.id,
        name=practice.name.value,
        method_id=practice.method_id,
        site_id=practice.site_id,
        status=practice.status.value,
        version=practice.version,
        created_at=timestamps.created_at if timestamps is not None else None,
        versioned_at=timestamps.versioned_at if timestamps is not None else None,
        deprecated_at=timestamps.deprecated_at if timestamps is not None else None,
    )
