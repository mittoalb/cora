"""HTTP route for the `get_family` query slice.

`GET /families/{family_id}` returns 200 + FamilyResponse
on hit, 404 on miss. The handler returns `Family | None`; the
route maps None to 404 via HTTPException (idiomatic in routes; the
BC's exception-handler infrastructure stays focused on domain /
application errors raised deeper in the stack).
"""

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
    """

    id: UUID
    name: str = Field(..., max_length=FAMILY_NAME_MAX_LENGTH)
    status: str
    version: str | None
    affordances: list[Affordance]


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
    family = await handler(
        GetFamily(family_id=family_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if family is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Family {family_id} not found",
        )
    return FamilyResponse(
        id=family.id,
        name=family.name.value,
        status=family.status.value,
        version=family.version,
        affordances=sorted(family.affordances, key=lambda a: a.value),
    )
