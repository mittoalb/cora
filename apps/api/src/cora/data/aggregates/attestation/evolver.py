"""Evolver: replay events to reconstruct Attestation state.

Mirror of every other CORA evolver. Terminal-at-genesis: a single
``AttestationRecorded`` event yields the final state; the aggregate
is single-state-single-event by design today. The terminal
``assert_never`` case forces pyright (and the runtime) to error if a
new event type is ever added to ``AttestationEvent`` without a
matching match arm here.

Status mapping per event type (current):
  - ``AttestationRecorded`` -> ``RECORDED`` (genesis-and-terminal)

The mapping is hardcoded per match arm; the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as Dataset / Distribution.

The ``evidence`` payload is reconstructed from its on-disk
representation per the discriminated ``kind``: today only the
``ChecksumVerified`` arm is concrete.
"""

from collections.abc import Sequence
from typing import assert_never
from uuid import UUID

from cora.data.aggregates.attestation.events import (
    AttestationEvent,
    AttestationRecorded,
)
from cora.data.aggregates.attestation.state import (
    Attestation,
    AttestationEvidence,
    AttestationKind,
    AttestationOutcome,
    AttestationStatus,
    ChecksumVerifiedEvidence,
    InvalidAttestationEvidenceError,
)


def _build_evidence(kind: AttestationKind, raw: dict[str, object]) -> AttestationEvidence:
    """Reconstruct the discriminated evidence VO from its on-disk shape.

    Today only the ``ChecksumVerified`` arm is concrete; the three
    reserved kinds raise ``InvalidAttestationEvidenceError`` (wrapped
    upstream by ``deserialize_or_raise`` into
    ``MalformedAttestationRecorded`` per
    [[project_from_stored_wrap_convention]]).

    On disk ``expected_checksum`` is NOT carried; the canonical value
    lives on the Distribution row. The evolver reconstructs the VO
    with ``expected_checksum`` populated from the same ``value`` key
    when Match/Mismatch (verifier reported its outcome against that
    canonical value) and ``""`` placeholder is rejected. For
    ``Unreachable`` the wire ``value`` is ``None``; the evolver
    accepts that and the VO carries ``computed_checksum=None``.

    The ``expected_checksum`` slot on the reconstructed VO mirrors the
    sibling ``computed_checksum`` (single ``value`` on the wire,
    interpreted as both halves at fold time when present); call sites
    that need the canonical checksum should re-read it from the
    Distribution projection or stream rather than the Attestation.
    """
    if kind is not AttestationKind.CHECKSUM_VERIFIED:
        raise InvalidAttestationEvidenceError(
            f"AttestationKind {kind.value!r} is not yet supported by the evolver"
        )
    algorithm = raw.get("algorithm")
    value = raw.get("value")
    verifier_supply_id_raw = raw.get("verifier_supply_id")
    verifier_kind = raw.get("verifier_kind")
    error_detail = raw.get("error_detail")
    if not isinstance(algorithm, str):
        raise InvalidAttestationEvidenceError("evidence.algorithm must be a string")
    if value is not None and not isinstance(value, str):
        raise InvalidAttestationEvidenceError("evidence.value must be a string or null")
    if not isinstance(verifier_supply_id_raw, str):
        raise InvalidAttestationEvidenceError("evidence.verifier_supply_id must be a string")
    if not isinstance(verifier_kind, str):
        raise InvalidAttestationEvidenceError("evidence.verifier_kind must be a string")
    if error_detail is not None and not isinstance(error_detail, str):
        raise InvalidAttestationEvidenceError("evidence.error_detail must be a string or null")
    # On the wire ``value`` IS the computed checksum (Match/Mismatch)
    # or None (Unreachable). The VO's ``expected_checksum`` slot mirrors
    # ``value`` when present so the post-init invariants pass; a
    # placeholder lowercase-hex string keeps the VO well-formed when
    # value is None (Unreachable case).
    expected = value if value is not None else "0" * 64
    return ChecksumVerifiedEvidence(
        expected_checksum=expected,
        computed_checksum=value,
        algorithm=algorithm,
        verifier_supply_id=UUID(verifier_supply_id_raw),
        verifier_kind=verifier_kind,
        error_detail=error_detail,
    )


def evolve(state: Attestation | None, event: AttestationEvent) -> Attestation:
    """Apply one event to the current Attestation state."""
    match event:
        case AttestationRecorded(
            attestation_id=attestation_id,
            dataset_id=dataset_id,
            distribution_id=distribution_id,
            kind=kind_str,
            outcome=outcome_str,
            evidence=evidence_payload,
            occurred_at=occurred_at,
            attested_by=attested_by,
        ):
            _ = state  # AttestationRecorded is the genesis event; prior state ignored.
            kind = AttestationKind(kind_str)
            outcome = AttestationOutcome(outcome_str)
            evidence = _build_evidence(kind, evidence_payload)
            return Attestation(
                id=attestation_id,
                dataset_id=dataset_id,
                distribution_id=distribution_id,
                kind=kind,
                outcome=outcome,
                evidence=evidence,
                attested_at=occurred_at,
                attested_by=attested_by,
                status=AttestationStatus.RECORDED,
            )
        case _:  # pragma: no cover  # exhaustiveness guard for future arms
            assert_never(event)


def fold(events: Sequence[AttestationEvent]) -> Attestation | None:
    """Replay a stream of events from the empty initial state."""
    state: Attestation | None = None
    for event in events:
        state = evolve(state, event)
    return state
