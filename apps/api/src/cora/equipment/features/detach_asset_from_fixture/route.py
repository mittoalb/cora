"""HTTP route for the `detach_asset_from_fixture` slice.

POST /assets/{asset_id}/detach-from-fixture: clear the Asset's
fixture_id back-reference (asset becomes detached). 204 No Content
on success.

Symmetric with attach: the body carries the fixture_id the operator
believes the Asset is currently attached to (defensive race-
condition guard).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.detach_asset_from_fixture.command import DetachAssetFromFixture
from cora.equipment.features.detach_asset_from_fixture.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class DetachAssetFromFixtureRequest(BaseModel):
    """Body for `POST /assets/{asset_id}/detach-from-fixture`."""

    fixture_id: UUID = Field(
        ...,
        description=(
            "Fixture.id the Asset is expected to be currently attached "
            "to. Defensive race-condition guard: if the Asset is "
            "actually attached to a different Fixture, the request is "
            "rejected."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.detach_asset_from_fixture
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/detach-from-fixture",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Asset does not exist.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Asset is not attached to any Fixture (strict-not-"
                "idempotent re-detach), OR Asset is attached to a "
                "different Fixture than the requested fixture_id "
                "(defensive race-condition guard), OR a concurrent "
                "write to the Asset stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation.",
        },
    },
    summary="Detach an Asset from the Fixture it is currently attached to",
)
async def post_assets_detach_from_fixture(
    asset_id: Annotated[UUID, Path(description="Target Asset's id.")],
    body: DetachAssetFromFixtureRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DetachAssetFromFixture(asset_id=asset_id, fixture_id=body.fixture_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
