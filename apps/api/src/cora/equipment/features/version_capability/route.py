"""HTTP route for the `version_capability` slice.

Action endpoint at `POST /capabilities/{capability_id}/version`.
Body carries `version_tag`. 204 No Content on success. Same
action-endpoint pattern as the other transition slices.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.capability import CAPABILITY_VERSION_TAG_MAX_LENGTH
from cora.equipment.features.version_capability.command import VersionCapability
from cora.equipment.features.version_capability.handler import Handler
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


class VersionCapabilityRequest(BaseModel):
    """Body for `POST /capabilities/{capability_id}/version`."""

    version_tag: str = Field(
        ...,
        min_length=1,
        max_length=CAPABILITY_VERSION_TAG_MAX_LENGTH,
        description=(
            "Operator-supplied label for this revision (for example "
            "'v2', '2026-Q3'). Free text; institution-specific."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.version_capability
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/capabilities/{capability_id}/version",
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
            "description": "No capability exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Capability is not in `Defined` or `Versioned` status "
                "(version requires one of those), OR a concurrent write "
                "to the same capability stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": ("Path parameter or request body failed schema validation."),
        },
    },
    summary="Issue a new version label for an existing capability",
)
async def post_capabilities_version(
    capability_id: Annotated[UUID, Path(description="Target capability's id.")],
    body: VersionCapabilityRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        VersionCapability(capability_id=capability_id, version_tag=body.version_tag),
        principal_id=principal_id,
        correlation_id=cid,
    )
