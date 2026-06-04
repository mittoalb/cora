"""HTTP route for the `get_fixture` query slice.

`GET /fixtures/{fixture_id}` returns 200 + FixtureResponse on hit,
404 on miss. The handler returns `Fixture | None`; the route maps
None to 404 via HTTPException.

Returns the FULL Fixture state: assembly_id + assembly_content_hash
snapshot + surface_id + slot_asset_bindings + parameter_overrides +
registered_at. Per-id reads use the event fold (source of truth);
list-level scans use the projection (list_fixtures).
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.get_fixture.handler import Handler
from cora.equipment.features.get_fixture.query import GetFixture
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class SlotAssetBindingResponse(BaseModel):
    """A single (slot_name, asset_id) binding within a Fixture."""

    slot_name: str
    asset_id: UUID


class FixtureResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. slot_asset_bindings serializes
    as a sorted list of binding objects (sorted by slot_name then
    asset_id for response determinism; frozenset semantics in domain
    state, list at the JSON boundary).
    """

    id: UUID
    assembly_id: UUID
    assembly_content_hash: str
    surface_id: UUID
    slot_asset_bindings: list[SlotAssetBindingResponse] = Field(
        default_factory=list[SlotAssetBindingResponse]
    )
    parameter_overrides: dict[str, Any] = Field(default_factory=dict[str, Any])
    registered_at: datetime | None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.get_fixture
    return handler


router = APIRouter(tags=["equipment"])


@router.get(
    "/fixtures/{fixture_id}",
    status_code=status.HTTP_200_OK,
    response_model=FixtureResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Fixture exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a Fixture by id",
)
async def get_fixtures(
    fixture_id: Annotated[UUID, Path(description="Target Fixture's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> FixtureResponse:
    fixture = await handler(
        GetFixture(fixture_id=fixture_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if fixture is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fixture {fixture_id} not found",
        )
    bindings = sorted(
        (
            SlotAssetBindingResponse(slot_name=b.slot_name, asset_id=b.asset_id)
            for b in fixture.slot_asset_bindings
        ),
        key=lambda b: (b.slot_name, str(b.asset_id)),
    )
    return FixtureResponse(
        id=fixture.id,
        assembly_id=fixture.assembly_id,
        assembly_content_hash=fixture.assembly_content_hash,
        surface_id=fixture.surface_id,
        slot_asset_bindings=bindings,
        parameter_overrides=fixture.parameter_overrides,
        registered_at=fixture.registered_at,
    )
