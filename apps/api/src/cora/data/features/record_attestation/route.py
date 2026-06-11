"""HTTP route for the ``record_attestation`` slice.

``POST /attestations`` returns 201 + ``RecordAttestationResponse`` on
success. Body carries the Attestation metadata: dual binding
(``dataset_id`` always, ``distribution_id`` optional), the kind /
outcome closed-enum values, and a nested ``evidence`` object whose
shape is discriminated by the sibling ``kind``.

## Flat route, nested evidence

Per [[project_data_attestation_design]] L21: REST route is the flat
``/attestations`` (NOT nested under ``/datasets/{id}/`` because an
Attestation may span Dataset OR Dataset+Distribution). Body shape uses
a nested ``evidence`` object to mirror the on-disk event payload (one
less translation surface for typed clients); the command object
flattens it.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.data.aggregates.attestation import (
    ATTESTATION_ERROR_DETAIL_MAX_LENGTH,
    ATTESTATION_VERIFIER_KIND_MAX_LENGTH,
    AttestationKind,
    AttestationOutcome,
)
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from cora.data.features.record_attestation.command import RecordAttestation
from cora.data.features.record_attestation.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class ChecksumVerifiedEvidenceRequest(BaseModel):
    """Nested evidence body for kind=ChecksumVerified."""

    algorithm: Literal["sha256"] = Field(
        ...,
        description=(
            "Checksum algorithm name. Only 'sha256' is accepted today; "
            "future algorithms add additional literal members."
        ),
    )
    expected_checksum: str = Field(
        ...,
        min_length=DATASET_CHECKSUM_SHA256_HEX_LENGTH,
        max_length=DATASET_CHECKSUM_SHA256_HEX_LENGTH,
        pattern="^[0-9a-f]{64}$",
        description="Canonical 64-char lowercase sha256 hex (the Distribution's expected value).",
    )
    computed_checksum: str | None = Field(
        default=None,
        min_length=DATASET_CHECKSUM_SHA256_HEX_LENGTH,
        max_length=DATASET_CHECKSUM_SHA256_HEX_LENGTH,
        pattern="^[0-9a-f]{64}$",
        description=(
            "Checksum the verifier computed. Required for outcome=Match or "
            "outcome=Mismatch; null only for outcome=Unreachable."
        ),
    )
    verifier_supply_id: UUID = Field(
        ...,
        description=(
            "Identifies the Supply (or other adapter-resident endpoint) "
            "the verifier walked. Forensic provenance."
        ),
    )
    verifier_kind: str = Field(
        ...,
        min_length=1,
        max_length=ATTESTATION_VERIFIER_KIND_MAX_LENGTH,
        description=("Short adapter name (e.g. 'HttpRangeChecksum'). Forensic provenance."),
    )
    error_detail: str | None = Field(
        default=None,
        min_length=1,
        max_length=ATTESTATION_ERROR_DETAIL_MAX_LENGTH,
        description=(
            "Human-readable failure summary. Required for outcome=Unreachable; null otherwise."
        ),
    )

    model_config = {"extra": "forbid"}


class RecordAttestationRequest(BaseModel):
    """Body for ``POST /attestations``."""

    dataset_id: UUID = Field(
        ...,
        description="Identifier of the Dataset the Attestation is about (always required).",
    )
    distribution_id: UUID | None = Field(
        default=None,
        description=(
            "Identifier of the bound Distribution byte-copy. Required for "
            "byte-level kinds (ChecksumVerified, FormatValidated, BitRotChecked); "
            "null only for ConformsToValidated."
        ),
    )
    kind: AttestationKind = Field(
        ...,
        description=(
            "What property was attested. Closed enum; today only 'ChecksumVerified' is implemented."
        ),
    )
    outcome: AttestationOutcome = Field(
        ...,
        description=("The outcome of the verifier run. Closed enum: Match, Mismatch, Unreachable."),
    )
    evidence: ChecksumVerifiedEvidenceRequest = Field(
        ...,
        description=(
            "Per-kind evidence object. Today only the ChecksumVerified shape "
            "is concrete (the other three kinds are not yet supported)."
        ),
    )

    model_config = {"extra": "forbid"}


class RecordAttestationResponse(BaseModel):
    """Response body for ``POST /attestations``."""

    attestation_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.data.record_attestation
    return handler


router = APIRouter(tags=["data"])


@router.post(
    "/attestations",
    status_code=status.HTTP_201_CREATED,
    response_model=RecordAttestationResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: malformed evidence VO, "
                "unsupported algorithm, kind not yet implemented in this "
                "release."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "Cross-aggregate reference does not exist: dataset_id or "
                "distribution_id (when provided)."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Dual-binding violation (kind requires/forbids "
                "distribution_id; Distribution's parent Dataset does not "
                "match; verifier evidence contradicts Distribution canonical "
                "checksum) or strict-not-idempotent same-id re-issue."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Record a new Attestation fact",
)
async def post_attestations(
    body: RecordAttestationRequest,
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
                "response instead of re-recording the Attestation."
            ),
        ),
    ] = None,
) -> RecordAttestationResponse:
    attestation_id = await handler(
        RecordAttestation(
            dataset_id=body.dataset_id,
            distribution_id=body.distribution_id,
            kind=body.kind.value,
            outcome=body.outcome.value,
            evidence_expected_checksum=body.evidence.expected_checksum,
            evidence_computed_checksum=body.evidence.computed_checksum,
            evidence_algorithm=body.evidence.algorithm,
            evidence_verifier_supply_id=body.evidence.verifier_supply_id,
            evidence_verifier_kind=body.evidence.verifier_kind,
            evidence_error_detail=body.evidence.error_detail,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RecordAttestationResponse(attestation_id=attestation_id)
