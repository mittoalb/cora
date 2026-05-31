"""HTTP route for the `initialize_seal` slice.

`POST /federation/seals` with body carrying facility_id +
online_credential_id + offline_credential_id. Returns 201 +
`{seal_stream_id, facility_id}` on success. The Seal singleton is
keyed on the human-readable facility_id (str); the response
additionally surfaces the deterministic stream UUID derived via
UUID5 so callers can address the stream directly when polling
read-side surfaces.

Per sec-4 AH#15 strengthening the decider invokes the
`_key_separation` helper against the prospective post-state;
`online_credential_id == offline_credential_id` is rejected with HTTP 422.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.federation.features.initialize_seal.command import InitializeSeal
from cora.federation.features.initialize_seal.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class InitializeSealRequest(BaseModel):
    """Body for `POST /federation/seals`."""

    facility_id: str = Field(
        ...,
        min_length=1,
        description=(
            "Opaque string id of the facility this Seal binds to. Facility "
            "identity is external to CORA; we do NOT mint facility ids. "
            "Doubles as the singleton identity (one Seal per facility)."
        ),
    )
    online_credential_id: UUID = Field(
        ...,
        description=(
            "Credential.id of the warm signing key (purpose SealOnlineSigning). "
            "Must differ from offline_credential_id."
        ),
    )
    offline_credential_id: UUID = Field(
        ...,
        description=(
            "Credential.id of the cold root key (purpose SealOfflineRoot). "
            "Must differ from online_credential_id."
        ),
    )

    model_config = {"extra": "forbid"}


class InitializeSealResponse(BaseModel):
    """Response body for `POST /federation/seals`."""

    seal_stream_id: UUID
    facility_id: str


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.federation.initialize_seal
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/seals",
    status_code=status.HTTP_201_CREATED,
    response_model=InitializeSealResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (whitespace-only facility_id).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "The Seal singleton for this facility already exists (stream has prior events)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": (
                "Request body failed schema validation (missing field, "
                "malformed UUID), OR online_credential_id equals offline_credential_id "
                "(key-separation invariant), OR Idempotency-Key was reused "
                "with a different request body."
            ),
        },
    },
    summary=(
        "Initialize the per-facility Seal singleton (cross-BC atomic; "
        "emits DecisionRegistered audit)"
    ),
)
async def post_federation_seals(
    body: InitializeSealRequest,
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
                "response instead of writing a duplicate Seal."
            ),
        ),
    ] = None,
) -> InitializeSealResponse:
    stream_id = await handler(
        InitializeSeal(
            facility_id=body.facility_id,
            online_credential_id=body.online_credential_id,
            offline_credential_id=body.offline_credential_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return InitializeSealResponse(seal_stream_id=stream_id, facility_id=body.facility_id)
