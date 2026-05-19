"""Unit tests for the Dataset evolver.

7a ships one event arm (DatasetRegistered → REGISTERED). The
exhaustiveness guard (assert_never) makes this test set tiny but
locks the genesis arm's shape.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DatasetDiscarded,
    DatasetPromoted,
    DatasetRegistered,
    DatasetStatus,
    Intent,
    evolve,
    fold,
)

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_registered_creates_dataset_with_registered_status() -> None:
    dataset_id = uuid4()
    event = DatasetRegistered(
        dataset_id=dataset_id,
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=42,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
    )
    state = evolve(state=None, event=event)
    assert state.id == dataset_id
    assert state.name.value == "D"
    assert state.uri.value == "s3://b/k"
    assert state.checksum.algorithm == "sha256"
    assert state.checksum.value == _GOOD_SHA256
    assert state.byte_size == 42
    assert state.encoding.media_type == "application/x-hdf5"
    assert state.encoding.conforms_to == frozenset()
    assert state.producing_run_id is None
    assert state.subject_id is None
    assert state.derived_from == frozenset()
    assert state.status is DatasetStatus.REGISTERED


@pytest.mark.unit
def test_evolve_preserves_optional_refs() -> None:
    run_id = uuid4()
    subject_id = uuid4()
    derived = uuid4()
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset({"https://manual.nexusformat.org/"}),
        producing_run_id=run_id,
        subject_id=subject_id,
        derived_from=frozenset({derived}),
        occurred_at=_NOW,
    )
    state = evolve(state=None, event=event)
    assert state.producing_run_id == run_id
    assert state.subject_id == subject_id
    assert state.derived_from == frozenset({derived})
    assert state.encoding.conforms_to == frozenset({"https://manual.nexusformat.org/"})


@pytest.mark.unit
def test_fold_empty_stream_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_register_event_returns_dataset() -> None:
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
    )
    state = fold([event])
    assert state is not None
    assert state.status is DatasetStatus.REGISTERED


# ---------- Phase 7e: intent + producing_run_end_state on DatasetRegistered ----------


@pytest.mark.unit
def test_evolve_registered_defaults_intent_to_trial() -> None:
    """New Datasets land in Trial intent on registration."""
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
    )
    state = evolve(state=None, event=event)
    assert state.intent is Intent.TRIAL
    assert state.producing_run_end_state is None


@pytest.mark.unit
def test_evolve_registered_captures_producing_run_end_state_when_provided() -> None:
    """When the handler captured the Run's end_state at registration,
    the evolver carries it through to state."""
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=uuid4(),
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        producing_run_end_state="Completed",
    )
    state = evolve(state=None, event=event)
    assert state.producing_run_end_state == "Completed"


# ---------- Phase 7e: DatasetPromoted arm ----------


def _registered_event() -> DatasetRegistered:
    return DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_evolve_promoted_flips_intent_to_production() -> None:
    """DatasetPromoted arm: intent goes Trial -> Production; status preserved."""
    register = _registered_event()
    promoted = DatasetPromoted(
        dataset_id=register.dataset_id,
        reason="passed review",
        occurred_at=_NOW,
    )
    state = fold([register, promoted])
    assert state is not None
    assert state.intent is Intent.PRODUCTION
    # Status preserved (intent is orthogonal to lifecycle).
    assert state.status is DatasetStatus.REGISTERED


@pytest.mark.unit
def test_evolve_discarded_after_promoted_preserves_intent() -> None:
    """Carry-through invariant: DatasetDiscarded preserves intent
    (audit-relevant historical artifact)."""
    register = _registered_event()
    promoted = DatasetPromoted(
        dataset_id=register.dataset_id,
        reason="passed review",
        occurred_at=_NOW,
    )
    discarded = DatasetDiscarded(
        dataset_id=register.dataset_id,
        reason="bytes purged",
        occurred_at=_NOW,
    )
    state = fold([register, promoted, discarded])
    assert state is not None
    assert state.status is DatasetStatus.DISCARDED
    # Intent preserved across discard (we keep the audit signal that
    # this was once promoted to Production).
    assert state.intent is Intent.PRODUCTION


@pytest.mark.unit
def test_evolve_promoted_raises_on_empty_state() -> None:
    """Defensive guard: DatasetPromoted requires prior state."""
    promoted = DatasetPromoted(
        dataset_id=uuid4(),
        reason="trying",
        occurred_at=_NOW,
    )
    with pytest.raises(ValueError, match="DatasetPromoted"):
        evolve(state=None, event=promoted)


@pytest.mark.unit
def test_evolve_discarded_preserves_producing_run_end_state() -> None:
    """Critical pin: DatasetDiscarded carries producing_run_end_state
    through. A regression that drops this field on discard would
    silently break audit fidelity (we lose the ability to reason
    about which Datasets came from Completed vs Aborted Runs after
    they're discarded)."""
    register = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=uuid4(),
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        producing_run_end_state="Completed",
    )
    discarded = DatasetDiscarded(
        dataset_id=register.dataset_id,
        reason="bytes purged",
        occurred_at=_NOW,
    )
    state = fold([register, discarded])
    assert state is not None
    assert state.status is DatasetStatus.DISCARDED
    # The captured Run end-state survives discard for audit fidelity.
    assert state.producing_run_end_state == "Completed"


@pytest.mark.unit
def test_evolve_promoted_preserves_producing_run_end_state() -> None:
    """Pin: DatasetPromoted carries producing_run_end_state through.
    The promoted-then-discarded chain preserves it (already covered
    above); pin the promoted-only case explicitly to defend the
    intermediate evolver arm."""
    register = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=uuid4(),
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        producing_run_end_state="Completed",
    )
    promoted = DatasetPromoted(
        dataset_id=register.dataset_id,
        reason="passed review",
        occurred_at=_NOW,
    )
    state = fold([register, promoted])
    assert state is not None
    assert state.intent is Intent.PRODUCTION
    assert state.producing_run_end_state == "Completed"


# ---------- Phase 12c: Dataset.used_calibrations AsShot citation ----------


from uuid import UUID  # noqa: E402


@pytest.mark.unit
def test_register_genesis_populates_used_calibrations_as_frozenset() -> None:
    """DatasetRegistered carries the tuple on the event payload; the
    evolver coerces to frozenset for in-memory equality semantics
    (mirrors Phase 12b Run.pinned_calibrations exactly)."""
    cal_a = UUID("01900000-0000-7000-8000-00000000ca01")
    cal_b = UUID("01900000-0000-7000-8000-00000000ca02")
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        used_calibrations=(cal_a, cal_b),
    )
    state = evolve(state=None, event=event)
    assert state.used_calibrations == frozenset({cal_a, cal_b})


@pytest.mark.unit
def test_legacy_pre_12c_register_folds_with_empty_used_calibrations() -> None:
    """Pre-12c DatasetRegistered events have no used_calibrations
    field (defaults to empty tuple via the additive-state pattern).
    They MUST fold to an empty frozenset — additive backward-compat
    contract mirrors derived_from / producing_run_end_state / intent
    precedent."""
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
    )
    state = evolve(state=None, event=event)
    assert state.used_calibrations == frozenset()


@pytest.mark.unit
def test_discard_preserves_used_calibrations_asshot_invariant() -> None:
    """Phase 12c AsShot invariant: terminal discard MUST preserve the
    citation set verbatim. A regression that wiped it would silently
    break 'what calibration revisions did this Dataset use?' queries
    forever even for the discarded-metadata audit trail."""
    cal_a = UUID("01900000-0000-7000-8000-00000000ca01")
    cal_b = UUID("01900000-0000-7000-8000-00000000ca02")
    register = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        used_calibrations=(cal_a, cal_b),
    )
    discarded = DatasetDiscarded(
        dataset_id=register.dataset_id,
        reason="bytes purged",
        occurred_at=_NOW,
    )
    state = fold([register, discarded])
    assert state is not None
    assert state.status is DatasetStatus.DISCARDED
    assert state.used_calibrations == frozenset({cal_a, cal_b})


@pytest.mark.unit
def test_promote_preserves_used_calibrations_asshot_invariant() -> None:
    """Phase 12c AsShot invariant: intent flip MUST preserve the
    citation set verbatim. Mirrors the discard-arm preserve test;
    same silent-wipe risk if a future evolver refactor swaps to
    dataclasses.replace and drops a field add."""
    cal_a = UUID("01900000-0000-7000-8000-00000000ca01")
    register = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        used_calibrations=(cal_a,),
    )
    promoted = DatasetPromoted(
        dataset_id=register.dataset_id,
        reason="passed review",
        occurred_at=_NOW,
    )
    state = fold([register, promoted])
    assert state is not None
    assert state.intent is Intent.PRODUCTION
    assert state.used_calibrations == frozenset({cal_a})
