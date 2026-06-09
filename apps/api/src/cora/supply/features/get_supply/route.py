"""HTTP route for the `get_supply` query slice.

`GET /supplies/{supply_id}` returns 200 + SupplyResponse on hit, 404
on miss. The handler returns `Supply | None`; the route maps None to
404 via HTTPException (idiomatic in routes; the BC's exception-
handler infrastructure stays focused on domain / application errors
raised deeper in the stack).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.facility_code import FACILITY_CODE_MAX_LENGTH
from cora.supply.aggregates.supply import (
    SUPPLY_KIND_MAX_LENGTH,
    SUPPLY_NAME_MAX_LENGTH,
    SupplyScope,
    SupplyStatus,
)
from cora.supply.features.get_supply.handler import Handler
from cora.supply.features.get_supply.query import GetSupply


class SupplyResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. Decouples the wire format
    from the domain model so the two can evolve independently.
    `scope` and `status` are the StrEnum string values; `kind` is the
    free-form bare-str discriminator (1-50 chars). `facility_code` is
    the cross-deployment convergent Facility slug surfaced as the
    bare-str wire value (Session 5 Slice 7A).
    """

    id: UUID
    scope: SupplyScope
    kind: str = Field(..., max_length=SUPPLY_KIND_MAX_LENGTH)
    name: str = Field(..., max_length=SUPPLY_NAME_MAX_LENGTH)
    facility_code: str = Field(..., max_length=FACILITY_CODE_MAX_LENGTH)
    containing_asset_id: UUID | None = Field(
        default=None,
        description=(
            "Id of the containing Asset (Equipment BC) when the Supply is bound "
            "to a Sector / Beamline / Unit; null for facility-scope resources "
            "(Session 5 Slice 7B)."
        ),
    )
    status: SupplyStatus


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.supply.get_supply
    return handler


router = APIRouter(tags=["supply"])


@router.get(
    "/supplies/{supply_id}",
    status_code=status.HTTP_200_OK,
    response_model=SupplyResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No supply exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a supply by id",
)
async def get_supplies(
    supply_id: Annotated[UUID, Path(description="Target supply's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> SupplyResponse:
    supply = await handler(
        GetSupply(supply_id=supply_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if supply is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supply {supply_id} not found",
        )
    return SupplyResponse(
        id=supply.id,
        scope=supply.scope,
        kind=supply.kind,
        name=supply.name.value,
        facility_code=supply.facility_code.value,
        containing_asset_id=supply.containing_asset_id,
        status=supply.status,
    )
