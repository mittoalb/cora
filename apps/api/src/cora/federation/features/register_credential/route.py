"""HTTP route for the `register_credential` slice.

`POST /federation/credentials` with body carrying facility_code +
audience + purpose + opaque secret_ref + optional
public_material_ref + optional expires_at. Returns 201 +
`{credential_id}` on success.

Per AH#6 of the locked design the body carries `secret_ref` as a
pre-existing opaque string (URI / KMS ARN / vault path); raw secret
bytes NEVER cross this wire. Operator tooling is responsible for
landing the bytes in the SecretStore adapter BEFORE invoking this
route.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.federation.aggregates.credential import CredentialPurpose
from cora.federation.features.register_credential.command import RegisterCredential
from cora.federation.features.register_credential.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class RegisterCredentialRequest(BaseModel):
    """Body for `POST /federation/credentials`."""

    facility_code: str = Field(
        ...,
        min_length=1,
        description=(
            "Cross-deployment convergent facility slug this credential binds to. "
            "Validated against the FacilityCode VO pattern (lowercase ASCII "
            "alphanumeric and dash, 1-32 chars) at the decider edge."
        ),
    )
    audience: str = Field(
        ...,
        min_length=1,
        description="Opaque string scoping the credential to a particular peer / endpoint.",
    )
    purpose: CredentialPurpose = Field(
        ...,
        description=(
            "Closed enum selecting which of the six roles this credential plays "
            "(Signing / Verification / Authentication / Encryption / "
            "SealOnlineSigning / SealOfflineRoot)."
        ),
    )
    secret_ref: str = Field(
        ...,
        min_length=1,
        description=(
            "Opaque pointer (URI / KMS ARN / vault path) to the secret material "
            "held in a SecretStore adapter. The aggregate NEVER carries raw "
            "secret bytes; the caller is responsible for landing bytes in "
            "SecretStore before invoking this slice."
        ),
    )
    public_material_ref: str | None = Field(
        default=None,
        description=(
            "Opaque pointer to the public counterpart when the purpose has one "
            "(verification key, encryption-public-key, certificate handle). "
            "None for symmetric purposes."
        ),
    )
    expires_at: datetime | None = Field(
        default=None,
        description=(
            "Optional contractual upper bound. When set, must lie strictly after the server's now."
        ),
    )

    model_config = {"extra": "forbid"}


class RegisterCredentialResponse(BaseModel):
    """Response body for `POST /federation/credentials`."""

    credential_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.federation.register_credential
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/credentials",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterCredentialResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (whitespace-only facility_code, audience, or "
                "secret_ref; or facility_code outside the FacilityCode pattern)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Defensive guard: the target Credential stream already has "
                "events. Essentially impossible in production with UUIDv7 ids."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": (
                "Request body failed schema validation (missing field, "
                "invalid enum value, malformed datetime), OR expires_at is "
                "set in the past, OR Idempotency-Key was reused with a "
                "different request body."
            ),
        },
    },
    summary=(
        "Register a new federation Credential (cross-BC atomic; emits DecisionRegistered audit)"
    ),
)
async def post_federation_credentials(
    body: RegisterCredentialRequest,
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
                "response instead of writing a duplicate Credential."
            ),
        ),
    ] = None,
) -> RegisterCredentialResponse:
    credential_id = await handler(
        RegisterCredential(
            facility_code=body.facility_code,
            audience=body.audience,
            purpose=body.purpose,
            secret_ref=body.secret_ref,
            public_material_ref=body.public_material_ref,
            expires_at=body.expires_at,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterCredentialResponse(credential_id=credential_id)
