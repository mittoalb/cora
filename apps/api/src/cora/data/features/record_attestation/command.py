"""The ``RecordAttestation`` command, intent dataclass for this slice.

Carries the caller-controlled inputs to record a new Attestation
fact: dual binding (``dataset_id`` always; ``distribution_id`` for
byte-level kinds), the kind / outcome closed-enum values, and the
flat per-kind evidence fields. The new ``attestation_id`` is
server-allocated by the handler from the IdGenerator port.

"Record" rather than "register" or "define": the fact-act exists in
the world already (the verifier walked the bytes and computed a
digest, or the operator observed conformance) and we are recording
it. Mirrors [[project_asset_condition_design]] precedent (degrade /
fault / restore are acts-of-record).

## Flat boundary, nested event payload

Per [[project_data_attestation_design]] L21: the REST + MCP Pydantic
boundary uses flat fields per-kind for wire ergonomics. The on-disk
event payload uses a nested ``evidence`` object discriminated by
``kind``. This command object accepts the flat boundary form; the
decider reconstructs the nested form before event emission.

## Strict-not-idempotent at same-stream-id

Per L14: same-stream-id re-issue raises ``AttestationAlreadyExistsError``.
No silent ``[]`` no-op. No cross-stream uniqueness constraint
(multiple Attestations for one tuple are first-class; nightly
re-checks are expected).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RecordAttestation:
    """Record a new Attestation fact with the given evidence.

    Today only ``kind == "ChecksumVerified"`` is supported; other kinds
    raise ``AttestationKindNotYetSupportedError`` at the handler tier.
    The ``evidence_*`` fields are flat per-kind; for ChecksumVerified
    they describe the verifier-port report.
    """

    dataset_id: UUID
    distribution_id: UUID | None
    kind: str
    outcome: str
    evidence_expected_checksum: str
    evidence_computed_checksum: str | None
    evidence_algorithm: str
    evidence_verifier_supply_id: UUID
    evidence_verifier_kind: str
    evidence_error_detail: str | None = None
