"""Domain events emitted by the Attestation aggregate plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated union,
``event_type_name``, ``to_payload``, ``from_stored``. The persistence-envelope
construction (``NewEvent``) lives at
``cora.infrastructure.event_envelope.to_new_event``.

## This module ships ONE event today

  - ``AttestationRecorded`` (genesis-and-terminal): a recorded fact
    about a Dataset (and optionally a Distribution byte-copy). Status
    is implicit (``Recorded``); the evolver sets it.

## Future events NAMED but not locked here

  - ``AttestationSuperseded`` (Recorded -> Superseded; future W3 if
    operators demand a corrective event).

## Payload conventions

- UUIDs serialize as strings; ``distribution_id`` may serialize as
  ``None`` (kind ``ConformsToValidated``).
- ``kind`` and ``outcome`` serialize as the StrEnum value bare-string.
- ``evidence`` serializes as a nested object whose shape is
  discriminated by the sibling ``kind`` field (NOT by a duplicated
  discriminator inside the sub-object). Today only the
  ``ChecksumVerified`` shape is concrete: ``{"algorithm": str,
  "value": str | None, "verifier_supply_id": str, "verifier_kind":
  str, "error_detail": str | None}``.
- ``occurred_at`` is the payload-time key per CORA convention; the
  in-memory state field is ``attested_at`` (mirrors Calibration
  ``occurred_at`` payload to ``established_at`` state precedent).
- Status is NOT carried in the payload; the event type encodes it
  (``AttestationRecorded`` -> ``RECORDED``).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.data.aggregates.attestation.state import (
    AttestationKind,
    AttestationOutcome,
    ChecksumVerifiedEvidence,
    InvalidAttestationEvidenceError,
    InvalidAttestationKindError,
    InvalidAttestationOutcomeError,
)
from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId


@dataclass(frozen=True)
class AttestationRecorded:
    """A new Attestation fact was recorded.

    Status is implicit (``Recorded``); the evolver sets it. The
    cross-aggregate references (``dataset_id`` always; ``distribution_id``
    when kind is byte-level) are eventual-consistency primitives; the
    handler pre-loads each on the write path, the evolver does NOT
    re-verify on fold.

    Per CONTRIBUTING.md "Primitives in event payloads": every field
    here is a primitive (str, int, UUID, datetime, dict-of-primitives).
    The discriminated VO is reconstructed by the evolver on fold; the
    decider unwraps it before constructing the event.

    Fold-symmetry attribution per [[project_fold_symmetry_design]]:
    ``attested_by: ActorId`` carries the envelope ``principal_id`` of
    the record-slice caller (``SYSTEM_PRINCIPAL_ID`` for verifier-port
    driven attestations; operator ``ActorId`` for operator-initiated
    re-verification).
    """

    attestation_id: UUID
    dataset_id: UUID
    distribution_id: UUID | None
    kind: str
    outcome: str
    evidence: dict[str, Any]
    occurred_at: datetime
    attested_by: ActorId


#: Discriminated union over Attestation events. Has one arm today;
#: future slices extend additively (W3 ``AttestationSuperseded`` only
#: if operator demand fires).
AttestationEvent = AttestationRecorded


def event_type_name(event: AttestationEvent) -> str:
    """Discriminator string written into ``StoredEvent.event_type``."""
    return type(event).__name__


def to_payload(event: AttestationEvent) -> dict[str, Any]:
    """Serialize an Attestation event to a JSON-friendly dict for jsonb storage."""
    match event:
        case AttestationRecorded(
            attestation_id=attestation_id,
            dataset_id=dataset_id,
            distribution_id=distribution_id,
            kind=kind,
            outcome=outcome,
            evidence=evidence,
            occurred_at=occurred_at,
            attested_by=attested_by,
        ):
            return {
                "attestation_id": str(attestation_id),
                "dataset_id": str(dataset_id),
                "distribution_id": (str(distribution_id) if distribution_id is not None else None),
                "kind": kind,
                "outcome": outcome,
                "evidence": dict(evidence),
                "occurred_at": occurred_at.isoformat(),
                "attested_by": str(attested_by),
            }
        case _:  # pragma: no cover  # exhaustiveness guard for future arms
            assert_never(event)


def from_stored(stored: StoredEvent) -> AttestationEvent:
    """Rebuild an Attestation event from a ``StoredEvent`` loaded from the event store.

    Dispatches on ``stored.event_type``; raises ``ValueError`` on
    unknown discriminators so a stream contaminated with foreign event
    types fails loud rather than silently being dropped by the
    evolver. Each per-event builder is wrapped in
    ``deserialize_or_raise`` to surface malformed payloads as
    ``MalformedAttestationRecorded`` per
    [[project_from_stored_wrap_convention]].
    """
    payload = stored.payload
    match stored.event_type:
        case "AttestationRecorded":

            def _build_recorded() -> AttestationRecorded:
                raw_distribution = payload["distribution_id"]
                kind_str = payload["kind"]
                outcome_str = payload["outcome"]
                # Defensive enum-membership re-checks (the wire payload is
                # bare-str; legacy or hand-crafted payloads with stale
                # values must fail loud at fold rather than poison state).
                try:
                    AttestationKind(kind_str)
                except ValueError as exc:
                    raise InvalidAttestationKindError(kind_str) from exc
                try:
                    AttestationOutcome(outcome_str)
                except ValueError as exc:
                    raise InvalidAttestationOutcomeError(outcome_str) from exc
                return AttestationRecorded(
                    attestation_id=UUID(payload["attestation_id"]),
                    dataset_id=UUID(payload["dataset_id"]),
                    distribution_id=(
                        UUID(raw_distribution) if raw_distribution is not None else None
                    ),
                    kind=kind_str,
                    outcome=outcome_str,
                    evidence=dict(payload["evidence"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    attested_by=ActorId(UUID(payload["attested_by"])),
                )

            return deserialize_or_raise(
                "AttestationRecorded",
                _build_recorded,
                extra=(
                    ValueError,
                    InvalidAttestationKindError,
                    InvalidAttestationOutcomeError,
                    InvalidAttestationEvidenceError,
                ),
            )
        case _:
            msg = f"Unknown AttestationEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


def build_checksum_verified_evidence_payload(
    evidence: ChecksumVerifiedEvidence,
) -> dict[str, Any]:
    """Serialize a ChecksumVerifiedEvidence VO into its on-disk shape.

    On disk the evidence carries a single ``value`` keyed by the
    sibling ``outcome`` discriminator: ``computed_checksum`` on
    Match/Mismatch, ``None`` on Unreachable. ``expected_checksum`` is
    NOT serialized (the canonical value lives on the Distribution
    row; storing it on the Attestation would create drift potential
    across re-checks).
    """
    payload: dict[str, Any] = {
        "algorithm": evidence.algorithm,
        "value": evidence.computed_checksum,
        "verifier_supply_id": str(evidence.verifier_supply_id),
        "verifier_kind": evidence.verifier_kind,
    }
    if evidence.error_detail is not None:
        payload["error_detail"] = evidence.error_detail
    return payload


__all__ = [
    "AttestationEvent",
    "AttestationRecorded",
    "build_checksum_verified_evidence_payload",
    "event_type_name",
    "from_stored",
    "to_payload",
]
