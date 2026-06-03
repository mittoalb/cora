"""HTTP route for the `define_permit` slice.

`POST /federation/permits` with body carrying peer_facility_id +
direction + the allowed-credential / payload-type / artifact-kind
scope sets + abi_tier_floor + expires_at + a discriminated `terms`
union (`OutboundTerms | InboundTerms`). Returns 201 + `{permit_id}`
on success.

`terms` arrives as a Pydantic discriminated union with a `kind`
field (`"Outbound" | "Inbound"`); the wire shape mirrors the jsonb
payload serializer at `federation.aggregates.permit.events`.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.federation.aggregates.permit import (
    AbiTier,
    Direction,
    InboundTerms,
    OnwardActionScope,
    OutboundTerms,
    ReadScope,
    ReceiptKind,
    ScopeRef,
)
from cora.federation.features.define_permit.command import DefinePermit
from cora.federation.features.define_permit.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class _ScopeRefRequest(BaseModel):
    """JSON wire shape for a `ScopeRef`."""

    kind: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    qualifier: str | None = None

    model_config = {"extra": "forbid"}


class _OutboundTermsRequest(BaseModel):
    """JSON wire shape for `OutboundTerms`."""

    kind: Literal["Outbound"]
    scopes: list[_ScopeRefRequest] = Field(..., min_length=1)
    read_scope: ReadScope
    onward_action_scope: OnwardActionScope

    model_config = {"extra": "forbid"}


class _InboundTermsRequest(BaseModel):
    """JSON wire shape for `InboundTerms`."""

    kind: Literal["Inbound"]
    inbound_allowed_artifact_kinds: list[str] = Field(..., min_length=1)
    accepted_canonicalization_versions: list[str] | None = None
    required_receipt_kinds: list[ReceiptKind] = Field(default_factory=list[ReceiptKind])
    publisher_grant_correlation_handle: str | None = None

    model_config = {"extra": "forbid"}


_TermsRequest = Annotated[
    _OutboundTermsRequest | _InboundTermsRequest,
    Field(discriminator="kind"),
]


class DefinePermitRequest(BaseModel):
    """Body for `POST /federation/permits`."""

    peer_facility_id: str = Field(
        ...,
        min_length=1,
        description=(
            "Opaque string id of the peer facility. Federation peers are "
            "external entities; CORA does NOT mint their ids."
        ),
    )
    direction: Direction = Field(
        ...,
        description=(
            "Query-convenience discriminator mirroring `type(terms)`. "
            "Must match the `terms.kind` arm; the decider rejects mismatches."
        ),
    )
    allowed_credential_ids: list[UUID] = Field(
        ...,
        min_length=1,
        description="Bounded set of Credential ids permitted under this permit.",
    )
    allowed_payload_types: list[str] = Field(
        ...,
        min_length=1,
        description="Payload-type strings honored on either side of the relationship.",
    )
    allowed_artifact_kinds: list[str] = Field(
        ...,
        min_length=1,
        description="Artifact-kind strings honored on either side of the relationship.",
    )
    abi_tier_floor: AbiTier = Field(
        ...,
        description="Lowest tier the permit honors on either side.",
    )
    expires_at: datetime = Field(
        ...,
        description="Contractual upper bound; must lie strictly after the server's now.",
    )
    terms: _TermsRequest = Field(
        ...,
        description=(
            "Direction-specific contractual fields. Discriminated by `kind`: "
            "`Outbound` carries `scopes` + `read_scope` + "
            "`onward_action_scope`; `Inbound` carries "
            "`inbound_allowed_artifact_kinds` + optional canonicalization / receipt "
            "config."
        ),
    )

    model_config = {"extra": "forbid"}


class DefinePermitResponse(BaseModel):
    """Response body for `POST /federation/permits`."""

    permit_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.federation.define_permit
    return handler


def _build_terms(body: _TermsRequest) -> OutboundTerms | InboundTerms:
    if isinstance(body, _OutboundTermsRequest):
        return OutboundTerms(
            scopes=frozenset(
                ScopeRef(kind=s.kind, name=s.name, qualifier=s.qualifier) for s in body.scopes
            ),
            read_scope=body.read_scope,
            onward_action_scope=body.onward_action_scope,
        )
    if body.accepted_canonicalization_versions is None:
        return InboundTerms(
            inbound_allowed_artifact_kinds=frozenset(body.inbound_allowed_artifact_kinds),
            required_receipt_kinds=frozenset(body.required_receipt_kinds),
            publisher_grant_correlation_handle=body.publisher_grant_correlation_handle,
        )
    return InboundTerms(
        inbound_allowed_artifact_kinds=frozenset(body.inbound_allowed_artifact_kinds),
        accepted_canonicalization_versions=frozenset(body.accepted_canonicalization_versions),
        required_receipt_kinds=frozenset(body.required_receipt_kinds),
        publisher_grant_correlation_handle=body.publisher_grant_correlation_handle,
    )


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/permits",
    status_code=status.HTTP_201_CREATED,
    response_model=DefinePermitResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (empty peer_facility_id, empty "
                "scope sets, expires_at in the past, direction / terms "
                "mismatch, or whitespace-only payload-type / artifact-kind "
                "entry)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Defensive guard: the target Permit stream already has "
                "events. Essentially impossible in production with UUIDv7 "
                "ids."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": (
                "Request body failed schema validation (missing field, "
                "invalid enum value, malformed UUID, OutboundTerms scope "
                "collapse, unknown canonicalization version), OR "
                "Idempotency-Key was reused with a different request body."
            ),
        },
    },
    summary="Define a new federation Permit (cross-BC atomic; emits DecisionRegistered audit)",
)
async def post_federation_permits(
    body: DefinePermitRequest,
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
                "response instead of writing a duplicate Permit."
            ),
        ),
    ] = None,
) -> DefinePermitResponse:
    permit_id = await handler(
        DefinePermit(
            peer_facility_id=body.peer_facility_id,
            direction=body.direction,
            allowed_credential_ids=frozenset(body.allowed_credential_ids),
            allowed_payload_types=frozenset(body.allowed_payload_types),
            allowed_artifact_kinds=frozenset(body.allowed_artifact_kinds),
            abi_tier_floor=body.abi_tier_floor,
            expires_at=body.expires_at,
            terms=_build_terms(body.terms),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return DefinePermitResponse(permit_id=permit_id)
