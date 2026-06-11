"""Unit tests for the Attestation aggregate state, enums, and evidence VO.

Pins the closed StrEnum membership shapes and the ChecksumVerifiedEvidence
invariants. The fold-symmetry of the Attestation dataclass (attested_at /
attested_by) is asserted via the architecture fitness test; this file
focuses on per-class shape invariants.
"""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.attestation import (
    ATTESTATION_ERROR_DETAIL_MAX_LENGTH,
    ATTESTATION_VERIFIER_KIND_MAX_LENGTH,
    Attestation,
    AttestationKind,
    AttestationOutcome,
    AttestationStatus,
    ChecksumVerifiedEvidence,
    InvalidAttestationEvidenceError,
)
from cora.shared.identity import ActorId

_GOOD_SHA = "a" * 64
_OTHER_SHA = "b" * 64
_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def _good_evidence(**overrides: object) -> ChecksumVerifiedEvidence:
    base: dict[str, object] = {
        "expected_checksum": _GOOD_SHA,
        "computed_checksum": _GOOD_SHA,
        "algorithm": "sha256",
        "verifier_supply_id": uuid4(),
        "verifier_kind": "HttpRangeChecksum",
        "error_detail": None,
    }
    base.update(overrides)
    return ChecksumVerifiedEvidence(**base)  # type: ignore[arg-type]


# ---------- Status enum ----------


@pytest.mark.unit
def test_attestation_status_carries_only_recorded() -> None:
    assert set(AttestationStatus) == {AttestationStatus.RECORDED}
    assert AttestationStatus.RECORDED.value == "Recorded"


# ---------- Kind enum ----------


@pytest.mark.unit
def test_attestation_kind_carries_all_four_values_day_one() -> None:
    assert {k.value for k in AttestationKind} == {
        "ChecksumVerified",
        "FormatValidated",
        "ConformsToValidated",
        "BitRotChecked",
    }


# ---------- Outcome enum ----------


@pytest.mark.unit
def test_attestation_outcome_carries_all_three_values_day_one() -> None:
    assert {o.value for o in AttestationOutcome} == {"Match", "Mismatch", "Unreachable"}


# ---------- ChecksumVerifiedEvidence VO ----------


@pytest.mark.unit
def test_checksum_verified_evidence_accepts_good_match_shape() -> None:
    ev = _good_evidence()
    assert ev.expected_checksum == _GOOD_SHA
    assert ev.computed_checksum == _GOOD_SHA
    assert ev.algorithm == "sha256"
    assert ev.verifier_kind == "HttpRangeChecksum"
    assert ev.error_detail is None


@pytest.mark.unit
def test_checksum_verified_evidence_accepts_unreachable_shape() -> None:
    ev = _good_evidence(computed_checksum=None, error_detail="HEAD timeout after 30s")
    assert ev.computed_checksum is None
    assert ev.error_detail == "HEAD timeout after 30s"


@pytest.mark.unit
def test_checksum_verified_evidence_rejects_non_sha256_algorithm() -> None:
    with pytest.raises(InvalidAttestationEvidenceError):
        _good_evidence(algorithm="md5")


@pytest.mark.unit
def test_checksum_verified_evidence_rejects_short_expected_checksum() -> None:
    with pytest.raises(InvalidAttestationEvidenceError):
        _good_evidence(expected_checksum="a" * 63)


@pytest.mark.unit
def test_checksum_verified_evidence_rejects_uppercase_hex_value() -> None:
    with pytest.raises(InvalidAttestationEvidenceError):
        _good_evidence(computed_checksum="A" * 64)


@pytest.mark.unit
def test_checksum_verified_evidence_rejects_non_hex_value() -> None:
    with pytest.raises(InvalidAttestationEvidenceError):
        _good_evidence(computed_checksum="z" * 64)


@pytest.mark.unit
def test_checksum_verified_evidence_rejects_empty_verifier_kind() -> None:
    with pytest.raises(InvalidAttestationEvidenceError):
        _good_evidence(verifier_kind="   ")


@pytest.mark.unit
def test_checksum_verified_evidence_trims_verifier_kind() -> None:
    ev = _good_evidence(verifier_kind="  HttpRangeChecksum  ")
    assert ev.verifier_kind == "HttpRangeChecksum"


@pytest.mark.unit
def test_checksum_verified_evidence_rejects_overlong_verifier_kind() -> None:
    with pytest.raises(InvalidAttestationEvidenceError):
        _good_evidence(verifier_kind="a" * (ATTESTATION_VERIFIER_KIND_MAX_LENGTH + 1))


@pytest.mark.unit
def test_checksum_verified_evidence_rejects_empty_error_detail() -> None:
    with pytest.raises(InvalidAttestationEvidenceError):
        _good_evidence(error_detail="   ")


@pytest.mark.unit
def test_checksum_verified_evidence_rejects_overlong_error_detail() -> None:
    with pytest.raises(InvalidAttestationEvidenceError):
        _good_evidence(error_detail="a" * (ATTESTATION_ERROR_DETAIL_MAX_LENGTH + 1))


# ---------- Attestation dataclass ----------


@pytest.mark.unit
def test_attestation_defaults_status_to_recorded() -> None:
    att = Attestation(
        id=uuid4(),
        dataset_id=uuid4(),
        distribution_id=uuid4(),
        kind=AttestationKind.CHECKSUM_VERIFIED,
        outcome=AttestationOutcome.MATCH,
        evidence=_good_evidence(),
        attested_at=_NOW,
        attested_by=ActorId(UUID("01900000-0000-7000-8000-000000000001")),
    )
    assert att.status is AttestationStatus.RECORDED


@pytest.mark.unit
def test_attestation_is_frozen() -> None:
    att = Attestation(
        id=uuid4(),
        dataset_id=uuid4(),
        distribution_id=None,
        kind=AttestationKind.CHECKSUM_VERIFIED,
        outcome=AttestationOutcome.UNREACHABLE,
        evidence=_good_evidence(computed_checksum=None, error_detail="boom"),
        attested_at=_NOW,
        attested_by=ActorId(UUID("01900000-0000-7000-8000-000000000002")),
    )
    with pytest.raises(FrozenInstanceError):
        att.outcome = AttestationOutcome.MATCH  # type: ignore[misc]


@pytest.mark.unit
def test_attestation_allows_distribution_id_none_for_conforms_to_arm() -> None:
    """Smoke: dataclass accepts the ConformsToValidated shape even though
    the slice's decider does not yet emit it. Locks the field type
    today so the future Slice E lands additive."""
    att = Attestation(
        id=uuid4(),
        dataset_id=uuid4(),
        distribution_id=None,
        kind=AttestationKind.CHECKSUM_VERIFIED,  # the only ship-able kind today
        outcome=AttestationOutcome.UNREACHABLE,
        evidence=_good_evidence(computed_checksum=None, error_detail="x"),
        attested_at=_NOW,
        attested_by=ActorId(UUID("01900000-0000-7000-8000-000000000003")),
    )
    assert att.distribution_id is None


@pytest.mark.unit
def test_inequality_of_two_different_attestations() -> None:
    a = Attestation(
        id=uuid4(),
        dataset_id=uuid4(),
        distribution_id=uuid4(),
        kind=AttestationKind.CHECKSUM_VERIFIED,
        outcome=AttestationOutcome.MATCH,
        evidence=_good_evidence(),
        attested_at=_NOW,
        attested_by=ActorId(UUID("01900000-0000-7000-8000-000000000004")),
    )
    b = Attestation(
        id=uuid4(),
        dataset_id=uuid4(),
        distribution_id=uuid4(),
        kind=AttestationKind.CHECKSUM_VERIFIED,
        outcome=AttestationOutcome.MISMATCH,
        evidence=_good_evidence(computed_checksum=_OTHER_SHA),
        attested_at=_NOW,
        attested_by=ActorId(UUID("01900000-0000-7000-8000-000000000005")),
    )
    assert a != b
