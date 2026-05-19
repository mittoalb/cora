"""HTTP route for the `version_family` slice.

Action endpoint at `POST /families/{family_id}/version`.
Body carries `version_tag`. 204 No Content on success. Same
action-endpoint pattern as the other transition slices.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.family import FAMILY_VERSION_TAG_MAX_LENGTH, Affordance
from cora.equipment.features.version_family.command import VersionFamily
from cora.equipment.features.version_family.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class VersionFamilyRequest(BaseModel):
    """Body for `POST /families/{family_id}/version`."""

    version_tag: str = Field(
        ...,
        min_length=1,
        max_length=FAMILY_VERSION_TAG_MAX_LENGTH,
        description=(
            "Operator-supplied label for this revision (for example "
            "'v2', '2026-Q3'). Free text; institution-specific."
        ),
    )
    affordances: list[Affordance] = Field(
        ...,
        description=(
            "Replacement affordance set for the new version. A new "
            "version IS a new declaration; the supplied set REPLACES "
            "the prior affordance set wholesale (no diff/merge "
            "semantics). Supply `[]` explicitly to clear all "
            "affordances at this version."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.version_family
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/families/{family_id}/version",
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
            "description": "No family exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Family is not in `Defined` or `Versioned` status "
                "(version requires one of those), OR a concurrent write "
                "to the same family stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": ("Path parameter or request body failed schema validation."),
        },
    },
    summary="Issue a new version label for an existing family",
)
async def post_families_version(
    family_id: Annotated[UUID, Path(description="Target family's id.")],
    body: VersionFamilyRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        VersionFamily(
            family_id=family_id,
            version_tag=body.version_tag,
            affordances=frozenset(body.affordances),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
