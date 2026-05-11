"""HTTP route for the `deprecate_practice` slice.

Action endpoint at `POST /practices/{practice_id}/deprecate`. No
body. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.recipe.features.deprecate_practice.command import DeprecatePractice
from cora.recipe.features.deprecate_practice.handler import Handler


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.deprecate_practice
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/practices/{practice_id}/deprecate",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
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
                "(deprecate requires one of those — re-deprecating a "
                "Deprecated practice raises), OR a concurrent write to "
                "the same practice stream conflicted (optimistic "
                "concurrency)."
            ),
        },
    },
    summary="Mark an existing practice as deprecated",
)
async def post_practices_deprecate(
    practice_id: Annotated[UUID, Path(description="Target practice's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        DeprecatePractice(practice_id=practice_id),
        principal_id=principal_id,
        correlation_id=cid,
    )
