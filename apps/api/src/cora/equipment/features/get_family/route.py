"""HTTP route for the `get_family` query slice.

`GET /families/{family_id}` returns 200 + FamilyResponse
on hit, 404 on miss. The handler returns `FamilyView | None`; the
route maps None to 404 via HTTPException (idiomatic in routes; the
BC's exception-handler infrastructure stays focused on domain /
application errors raised deeper in the stack).

`created_at` / `versioned_at` / `deprecated_at` are sourced from the
`proj_equipment_family_summary` projection, not from aggregate state
(Path C, audit-2026-05-20 Iter B-3). Null semantics under eventual
consistency: read together with `status`. A 200 with a populated
`status` but null timestamp means projection lag, never a missing
transition. A 404 means the Family aggregate itself does not exist.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.family import FAMILY_NAME_MAX_LENGTH, Affordance
from cora.equipment.features.get_family.handler import Handler
from cora.equipment.features.get_family.query import GetFamily
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class FamilyResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. Decouples the wire format
    from the domain model so the two can evolve independently.
    `status` is the StrEnum's string value (Defined / Versioned /
    Deprecated). `version` is the operator-supplied label of the most
    recent version_family call (null until first version).
    `affordances` (5j) serializes as a sorted list of Affordance
    enum string values (frozenset semantics in domain state, list at
    the JSON boundary; sorted alphabetically for response determinism).
    `created_at` / `versioned_at` / `deprecated_at` are projection-
    sourced lifecycle timestamps (Path C, audit-2026-05-20 Iter B-3);
    see module docstring for null-semantics.
    """

    id: UUID
    name: str = Field(..., max_length=FAMILY_NAME_MAX_LENGTH)
    status: str
    version: str | None
    affordances: list[Affordance]
    created_at: datetime | None = None
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.get_family
    return handler


router = APIRouter(tags=["equipment"])


@router.get(
    "/families/{family_id}",
    status_code=status.HTTP_200_OK,
    response_model=FamilyResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No family exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a family by id",
)
async def get_families(
    family_id: Annotated[UUID, Path(description="Target family's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> FamilyResponse:
    view = await handler(
        GetFamily(family_id=family_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Family {family_id} not found",
        )
    family = view.family
    timestamps = view.timestamps
    return FamilyResponse(
        id=family.id,
        name=family.name.value,
        status=family.status.value,
        version=family.version,
        affordances=sorted(family.affordances, key=lambda a: a.value),
        created_at=timestamps.created_at if timestamps is not None else None,
        versioned_at=timestamps.versioned_at if timestamps is not None else None,
        deprecated_at=timestamps.deprecated_at if timestamps is not None else None,
    )
