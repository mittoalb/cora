"""HTTP route for the `list_fixtures` query slice.

`GET /fixtures?cursor=...&limit=50&assembly_id=...&surface_id=...&assembly_content_hash=...`
returns `{"items": [...], "next_cursor": "..." | null}`.

All three filters are optional and combinable. Each is backed by an
index from the B.4 fixture-summary migration.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel

from cora.equipment.features.list_fixtures.handler import Handler
from cora.equipment.features.list_fixtures.query import ListFixtures
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class FixtureSummaryDTO(BaseModel):
    """One Fixture in a paginated list (summary-only)."""

    fixture_id: UUID
    assembly_id: UUID
    assembly_content_hash: str
    surface_id: UUID
    binding_count: int
    override_count: int
    created_at: datetime


class FixtureListResponse(BaseModel):
    """Page of Fixtures plus opaque next-page cursor."""

    items: list[FixtureSummaryDTO]
    next_cursor: str | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.list_fixtures
    return handler


router = APIRouter(tags=["equipment"])


@router.get(
    "/fixtures",
    status_code=status.HTTP_200_OK,
    response_model=FixtureListResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Query parameters failed validation OR `cursor` was "
                "malformed (corrupt base64, missing separator, bad "
                "timestamp / UUID)."
            ),
        },
    },
    summary="List Fixtures with cursor pagination + assembly/surface/content_hash filters",
)
async def list_fixtures(
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    request_surface_id: Annotated[UUID, Depends(get_surface_id)],
    cursor: Annotated[
        str | None,
        Query(description="Opaque cursor from a previous page's `next_cursor`."),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Page size; capped at 100."),
    ] = 50,
    assembly_id: Annotated[
        UUID | None,
        Query(description="Only Fixtures of this Assembly blueprint."),
    ] = None,
    surface_id: Annotated[
        UUID | None,
        Query(description="Only Fixtures registered on this Trust Surface."),
    ] = None,
    assembly_content_hash: Annotated[
        str | None,
        Query(
            description=(
                "Only Fixtures whose snapshot matches this content_hash "
                "(cross-Surface federation queries)."
            ),
        ),
    ] = None,
) -> FixtureListResponse:
    page = await handler(
        ListFixtures(
            cursor=cursor,
            limit=limit,
            assembly_id=assembly_id,
            surface_id=surface_id,
            assembly_content_hash=assembly_content_hash,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=request_surface_id,
    )
    return FixtureListResponse(
        items=[
            FixtureSummaryDTO(
                fixture_id=item.fixture_id,
                assembly_id=item.assembly_id,
                assembly_content_hash=item.assembly_content_hash,
                surface_id=item.surface_id,
                binding_count=item.binding_count,
                override_count=item.override_count,
                created_at=item.created_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
