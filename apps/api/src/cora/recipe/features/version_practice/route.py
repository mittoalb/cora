"""HTTP route for the `version_practice` slice.

Action endpoint at `POST /practices/{practice_id}/version`. Body
carries `version_tag`. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.recipe.aggregates.practice import PRACTICE_VERSION_TAG_MAX_LENGTH
from cora.recipe.features.version_practice.command import VersionPractice
from cora.recipe.features.version_practice.handler import Handler


class VersionPracticeRequest(BaseModel):
    """Body for `POST /practices/{practice_id}/version`."""

    version_tag: str = Field(
        ...,
        min_length=1,
        max_length=PRACTICE_VERSION_TAG_MAX_LENGTH,
        description=(
            "Operator-supplied label for this revision (for example "
            "'v2', '2026-Q3'). Free text; institution-specific."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.version_practice
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/practices/{practice_id}/version",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": ("Domain invariant violated: whitespace-only version_tag."),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No practice exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Practice is not in `Defined` or `Versioned` status "
                "(version requires one of those), OR a concurrent write "
                "to the same practice stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": ("Path parameter or request body failed schema validation."),
        },
    },
    summary="Issue a new version label for an existing practice",
)
async def post_practices_version(
    practice_id: Annotated[UUID, Path(description="Target practice's id.")],
    body: VersionPracticeRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        VersionPractice(practice_id=practice_id, version_tag=body.version_tag),
        principal_id=principal_id,
        correlation_id=cid,
    )
