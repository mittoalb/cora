"""HTTP route for the `get_seal` query slice.

`GET /federation/seals/{facility_id}` returns 200 + `SealResponse` on
hit, 404 on miss. The Seal is a per-facility singleton keyed on the
human-readable `facility_id` (str); there is no separate seal_id in
the URL.

Per Path C, `initialized_at` / `last_signed_at` /
`last_signed_by_actor_id` are projection-sourced (not aggregate state)
and therefore nullable on the wire: the projection may transiently lag
behind the event store, or the deps may lack a configured pool
(in-memory test mode). Mirrors the Calibration / Credential read DTOs.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel

from cora.federation.aggregates.seal import Seal, SealStatus
from cora.federation.features.get_seal.handler import Handler
from cora.federation.features.get_seal.query import GetSeal
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class SealResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Mirrors the Seal aggregate state plus projection-sourced lifecycle
    timestamps. `online_key_ref` / `offline_key_ref` are Credential
    references (their referenced secrets never cross this wire).
    """

    facility_id: str
    online_key_ref: UUID
    offline_key_ref: UUID
    current_head_hash: str | None
    current_sequence_number: int
    initialized_by_actor_id: UUID
    status: SealStatus
    initialized_at: datetime | None = None
    last_signed_at: datetime | None = None
    last_signed_by_actor_id: UUID | None = None


def _response_from_view(
    seal: Seal,
    initialized_at: datetime | None,
    last_signed_at: datetime | None,
    last_signed_by_actor_id: UUID | None,
) -> SealResponse:
    return SealResponse(
        facility_id=seal.facility_id,
        online_key_ref=seal.online_key_ref,
        offline_key_ref=seal.offline_key_ref,
        current_head_hash=seal.current_head_hash,
        current_sequence_number=seal.current_sequence_number,
        initialized_by_actor_id=seal.initialized_by_actor_id,
        status=seal.status,
        initialized_at=initialized_at,
        last_signed_at=last_signed_at,
        last_signed_by_actor_id=last_signed_by_actor_id,
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.get_seal
    return handler


router = APIRouter(tags=["federation"])


@router.get(
    "/federation/seals/{facility_id}",
    status_code=status.HTTP_200_OK,
    response_model=SealResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Seal exists for the given facility.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get the per-facility Seal singleton",
)
async def get_federation_seal(
    facility_id: Annotated[
        str,
        Path(
            min_length=1,
            description="Target facility's opaque string id.",
        ),
    ],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> SealResponse:
    view = await handler(
        GetSeal(facility_id=facility_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seal for facility {facility_id!r} not found",
        )
    return _response_from_view(
        view.seal,
        view.timestamps.initialized_at if view.timestamps is not None else None,
        view.timestamps.last_signed_at if view.timestamps is not None else None,
        view.timestamps.last_signed_by_actor_id if view.timestamps is not None else None,
    )
