"""HTTP route for the `update_asset_settings` slice.

Action endpoint at `PATCH /assets/{asset_id}/settings`. Body
carries `settings_patch` — a partial dict applied with RFC 7396
JSON Merge Patch semantics. 204 No Content on success.

Uses HTTP PATCH (not POST-as-action like the condition slices)
because PATCH is the right verb for partial-update semantics on a
sub-resource. The body shape is `{settings_patch: {...}}` rather
than the patch dict directly so the request envelope can grow
additional fields (e.g. dry_run flag) in a future additive
revision without breaking clients.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.update_asset_settings.command import UpdateAssetSettings
from cora.equipment.features.update_asset_settings.handler import Handler
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


class UpdateAssetSettingsRequest(BaseModel):
    """Body for `PATCH /assets/{asset_id}/settings`.

    `settings_patch` is a dict applied with RFC 7396 (JSON Merge
    Patch) semantics:
      - keys with non-null values are set / replaced
      - keys with null are deleted from settings
      - absent keys are preserved

    The decider validates the post-merge result against the union
    of the Asset's currently-assigned Capabilities' settings_schemas
    (5g-a). Validation failure surfaces as HTTP 400.
    """

    settings_patch: dict[str, Any] = Field(
        ...,
        description=(
            "Partial settings dict. RFC 7396 merge semantics: "
            "non-null values set/replace; null values delete; "
            "absent keys are preserved."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.update_asset_settings
    return handler


router = APIRouter(tags=["equipment"])


@router.patch(
    "/assets/{asset_id}/settings",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "The proposed settings (after merge) failed cross-"
                "Family validation: an orphan key, a constraint "
                "violation, or a true type conflict between two "
                "Capabilities declaring the same key."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No asset exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "A concurrent write to the same asset stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing "
                "settings_patch field, malformed UUID in path, etc.)."
            ),
        },
    },
    summary="Update an existing asset's settings dict (RFC 7396 merge semantics)",
)
async def patch_asset_settings(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    body: UpdateAssetSettingsRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        UpdateAssetSettings(asset_id=asset_id, settings_patch=body.settings_patch),
        principal_id=principal_id,
        correlation_id=cid,
    )
