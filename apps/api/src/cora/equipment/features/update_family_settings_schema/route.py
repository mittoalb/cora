"""HTTP route for the `update_family_settings_schema` slice.

Action endpoint at `POST /families/{family_id}/settings-schema`.
Body carries the JSON Schema (or null to clear). 204 No Content on
success. Same action-endpoint pattern as the other transition
slices.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.update_family_settings_schema.command import (
    UpdateFamilySettingsSchema,
)
from cora.equipment.features.update_family_settings_schema.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class UpdateFamilySettingsSchemaRequest(BaseModel):
    """Body for `POST /families/{family_id}/settings-schema`."""

    settings_schema: dict[str, Any] | None = Field(
        ...,
        description=(
            "JSON Schema (Draft 2020-12, constrained subset) declaring "
            "the shape of Asset.settings keys this Family owns. "
            "Pass `null` to clear an existing schema. Subset allows "
            "only: $schema, type, required, properties, enum, minimum, "
            "maximum, pattern. The $schema field is required (must "
            "be 'https://json-schema.org/draft/2020-12/schema')."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.update_family_settings_schema
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/families/{family_id}/settings-schema",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Schema rejected: missing or wrong `$schema`, forbidden "
                "keyword (for example $ref / oneOf / allOf), or jsonschema-rs "
                "rejected the schema as malformed."
            ),
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
                "Concurrent write to the same family stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Set, replace, or clear a Family's settings_schema",
)
async def post_families_schema(
    family_id: Annotated[UUID, Path(description="Target family's id.")],
    body: UpdateFamilySettingsSchemaRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        UpdateFamilySettingsSchema(
            family_id=family_id,
            settings_schema=body.settings_schema,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
