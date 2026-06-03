"""HTTP route for the `attach_asset_to_fixture` slice.

POST /assets/{asset_id}/attach-to-fixture: bind an existing Asset to
a registered Fixture by recording the back-reference on the Asset
stream. 204 No Content on success.

Mirrors the action-style endpoint shape used by other Asset
mutations (`activate`, `decommission`, `add-family`, etc.).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.attach_asset_to_fixture.command import AttachAssetToFixture
from cora.equipment.features.attach_asset_to_fixture.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class AttachAssetToFixtureRequest(BaseModel):
    """Body for `POST /assets/{asset_id}/attach-to-fixture`."""

    fixture_id: UUID = Field(
        ...,
        description=(
            "Fixture.id this Asset will be bound into. Must resolve to "
            "a registered Fixture whose slot_asset_bindings include "
            "this asset_id."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.attach_asset_to_fixture
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/attach-to-fixture",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Asset does not appear in the Fixture's "
                "slot_asset_bindings (phantom back-reference rejected)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Asset or Fixture does not exist.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Asset is already attached to a Fixture (re-attach "
                "requires detach first), OR Asset is in a lifecycle "
                "that disallows attach (currently Decommissioned only), "
                "OR a concurrent write to the Asset stream conflicted "
                "(optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation.",
        },
    },
    summary="Bind an existing Asset to a registered Fixture",
)
async def post_assets_attach_to_fixture(
    asset_id: Annotated[UUID, Path(description="Target Asset's id.")],
    body: AttachAssetToFixtureRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        AttachAssetToFixture(asset_id=asset_id, fixture_id=body.fixture_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
