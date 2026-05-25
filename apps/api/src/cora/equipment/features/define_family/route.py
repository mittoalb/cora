"""HTTP route for the `define_family` slice.

Pydantic request/response schemas + APIRouter for `POST /families`.
The slice's BC-level wiring (`cora.equipment.routes.register_equipment_routes`)
includes this router on the FastAPI app.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.family import FAMILY_NAME_MAX_LENGTH, Affordance
from cora.equipment.features.define_family.command import DefineFamily
from cora.equipment.features.define_family.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class DefineFamilyRequest(BaseModel):
    """Body for `POST /families`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=FAMILY_NAME_MAX_LENGTH,
        description="Display name for the new Family.",
    )
    affordances: list[Affordance] = Field(
        ...,
        description=(
            "Closed-enum set of device-level operational primitives this "
            "Family supports. Required at definition time: "
            "supply `[]` explicitly when no v1 Affordance applies. "
            "Deduplicated server-side. See "
            "`cora.equipment.aggregates.family.affordance.Affordance` for "
            "the 28-item closed enum and the 3-pattern rule."
        ),
    )


class DefineFamilyResponse(BaseModel):
    """Response body for `POST /families`."""

    family_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.equipment.define_family
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/families",
    status_code=status.HTTP_201_CREATED,
    response_model=DefineFamilyResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (for example whitespace-only name).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Define a new technique-class family",
)
async def post_families(
    body: DefineFamilyRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied unique key per logical request. "
                "Retries with the same key + same body return the cached "
                "response instead of re-creating the family."
            ),
        ),
    ] = None,
) -> DefineFamilyResponse:
    family_id = await handler(
        DefineFamily(name=body.name, affordances=frozenset(body.affordances)),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return DefineFamilyResponse(family_id=family_id)
