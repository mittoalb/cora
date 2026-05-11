"""HTTP route for the `get_practice` query slice.

`GET /practices/{practice_id}` returns 200 + PracticeResponse on
hit, 404 on miss. The handler returns `Practice | None`; the route
maps None to 404 via HTTPException.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.recipe.aggregates.practice import PRACTICE_NAME_MAX_LENGTH
from cora.recipe.features.get_practice.handler import Handler
from cora.recipe.features.get_practice.query import GetPractice


class PracticeResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. `status` is the StrEnum's
    string value (Defined / Versioned / Deprecated).
    `current_version` is the operator-supplied label of the most
    recent version_practice call (null until first version, ships
    in 6d-2).
    """

    id: UUID
    name: str = Field(..., max_length=PRACTICE_NAME_MAX_LENGTH)
    method_id: UUID
    site_id: UUID
    status: str
    current_version: str | None


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
) -> PracticeResponse:
    practice = await handler(
        GetPractice(practice_id=practice_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
    if practice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Practice {practice_id} not found",
        )
    return PracticeResponse(
        id=practice.id,
        name=practice.name.value,
        method_id=practice.method_id,
        site_id=practice.site_id,
        status=practice.status.value,
        current_version=practice.current_version,
    )
