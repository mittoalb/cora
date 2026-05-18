"""HTTP route for the `version_method` slice.

Action endpoint at `POST /methods/{method_id}/version`. Body
carries `version_tag`. 204 No Content on success. Mirrors
`version_family`'s shape (Equipment 5f-2).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.recipe.aggregates.method import METHOD_VERSION_TAG_MAX_LENGTH
from cora.recipe.features.version_method.command import VersionMethod
from cora.recipe.features.version_method.handler import Handler


class VersionMethodRequest(BaseModel):
    """Body for `POST /methods/{method_id}/version`."""

    version_tag: str = Field(
        ...,
        min_length=1,
        max_length=METHOD_VERSION_TAG_MAX_LENGTH,
        description=(
            "Operator-supplied label for this revision (for example "
            "'v2', '2026-Q3'). Free text; institution-specific."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.version_method
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/methods/{method_id}/version",
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
            "description": "No method exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Method is not in `Defined` or `Versioned` status "
                "(version requires one of those), OR a concurrent write "
                "to the same method stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": ("Path parameter or request body failed schema validation."),
        },
    },
    summary="Issue a new version label for an existing method",
)
async def post_methods_version(
    method_id: Annotated[UUID, Path(description="Target method's id.")],
    body: VersionMethodRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        VersionMethod(method_id=method_id, version_tag=body.version_tag),
        principal_id=principal_id,
        correlation_id=cid,
    )
