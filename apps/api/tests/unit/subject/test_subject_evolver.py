"""Unit tests for the Subject aggregate's evolver."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.subject.aggregates.subject import (
    Subject,
    SubjectName,
    SubjectStatus,
    evolve,
    fold,
)
from cora.subject.aggregates.subject.events import (
    SubjectDiscarded,
    SubjectMeasured,
    SubjectMounted,
    SubjectRegistered,
    SubjectRemoved,
    SubjectReturned,
    SubjectStored,
)
from cora.subject.features import register_subject
from cora.subject.features.register_subject import RegisterSubject

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_ASSET_ID = UUID("01900000-0000-7000-8000-00000000a55e")


@pytest.mark.unit
def test_evolve_subject_registered_sets_status_to_received() -> None:
    """SubjectRegistered is the genesis event; status defaults to
    Received via the evolver. Pin so a future change (e.g., adding
    `initial_status` to the event payload) is a deliberate
    additive-state evolution."""
    subject_id = uuid4()
    state = evolve(
        None,
        SubjectRegistered(subject_id=subject_id, name="Sample-A1", occurred_at=_NOW),
    )
    assert state == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.RECEIVED
    )


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_subject_registered_returns_subject() -> None:
    subject_id = uuid4()
    state = fold([SubjectRegistered(subject_id=subject_id, name="Sample-A1", occurred_at=_NOW)])
    assert state == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.RECEIVED
    )


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    subject_id = uuid4()
    events = [SubjectRegistered(subject_id=subject_id, name="Sample-A1", occurred_at=_NOW)]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip() -> None:
    """The events the decider produces must rebuild the expected state."""
    new_id = uuid4()
    command = RegisterSubject(name="  Sample-A1  ")  # whitespace exercises the VO trim

    events = register_subject.decide(state=None, command=command, now=_NOW, new_id=new_id)
    rebuilt = fold(events)

    assert rebuilt == Subject(
        id=new_id, name=SubjectName("Sample-A1"), status=SubjectStatus.RECEIVED
    )


# ---------- SubjectMounted (Phase 4b) ----------


@pytest.mark.unit
def test_evolve_subject_mounted_flips_status_to_mounted() -> None:
    """SubjectMounted folded onto a Received subject sets status=MOUNTED.
    Status field is NOT in the event payload; the evolver derives it from
    the event TYPE (same precedent as ActorDeactivated -> is_active=False)."""
    subject_id = uuid4()
    received = Subject(id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.RECEIVED)
    mounted = evolve(received, SubjectMounted(subject_id=subject_id, asset_id=_ASSET_ID, occurred_at=_NOW))
    assert mounted == Subject(
        id=subject_id,
        name=SubjectName("Sample-A1"),
        status=SubjectStatus.MOUNTED,
        mounted_on_asset_id=_ASSET_ID,
    )


@pytest.mark.unit
def test_evolve_subject_mounted_preserves_id_and_name() -> None:
    """The evolver only updates `status`; id and name are carried over
    from prior state. Pinned so a future change that accidentally
    drops the name (e.g., refactor that builds Subject from event
    fields only) is caught."""
    subject_id = uuid4()
    received = Subject(id=subject_id, name=SubjectName("Original"), status=SubjectStatus.RECEIVED)
    mounted = evolve(received, SubjectMounted(subject_id=subject_id, asset_id=_ASSET_ID, occurred_at=_NOW))
    assert mounted.id == subject_id
    assert mounted.name == SubjectName("Original")


@pytest.mark.unit
def test_evolve_subject_mounted_on_empty_state_raises() -> None:
    """SubjectMounted before SubjectRegistered = corrupted stream.
    Fail loud rather than silently producing an empty subject."""
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, SubjectMounted(subject_id=uuid4(), asset_id=_ASSET_ID, occurred_at=_NOW))


@pytest.mark.unit
def test_fold_register_then_mount_yields_mounted_subject() -> None:
    """End-to-end fold: registration + mount produces a Mounted subject."""
    subject_id = uuid4()
    state = fold(
        [
            SubjectRegistered(subject_id=subject_id, name="Sample-A1", occurred_at=_NOW),
            SubjectMounted(subject_id=subject_id, asset_id=_ASSET_ID, occurred_at=_NOW),
        ]
    )
    assert state == Subject(
        id=subject_id,
        name=SubjectName("Sample-A1"),
        status=SubjectStatus.MOUNTED,
        mounted_on_asset_id=_ASSET_ID,
    )


# ---------- SubjectMeasured (Phase 4c) ----------


@pytest.mark.unit
def test_evolve_subject_measured_flips_status_to_measured() -> None:
    """SubjectMeasured folded onto a Mounted subject sets status=MEASURED.
    Status field is NOT in the event payload; the evolver derives it
    from the event TYPE (same precedent as SubjectMounted)."""
    subject_id = uuid4()
    mounted = Subject(id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.MOUNTED)
    measured = evolve(mounted, SubjectMeasured(subject_id=subject_id, occurred_at=_NOW))
    assert measured == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.MEASURED
    )


@pytest.mark.unit
def test_evolve_subject_measured_preserves_id_and_name() -> None:
    subject_id = uuid4()
    mounted = Subject(id=subject_id, name=SubjectName("Original"), status=SubjectStatus.MOUNTED)
    measured = evolve(mounted, SubjectMeasured(subject_id=subject_id, occurred_at=_NOW))
    assert measured.id == subject_id
    assert measured.name == SubjectName("Original")


@pytest.mark.unit
def test_evolve_subject_measured_on_empty_state_raises() -> None:
    """SubjectMeasured before SubjectRegistered = corrupted stream.
    Fail loud rather than silently producing an empty subject."""
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, SubjectMeasured(subject_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_fold_register_mount_measure_yields_measured_subject() -> None:
    """End-to-end fold: registration + mount + measure produces a Measured subject."""
    subject_id = uuid4()
    state = fold(
        [
            SubjectRegistered(subject_id=subject_id, name="Sample-A1", occurred_at=_NOW),
            SubjectMounted(subject_id=subject_id, asset_id=_ASSET_ID, occurred_at=_NOW),
            SubjectMeasured(subject_id=subject_id, occurred_at=_NOW),
        ]
    )
    assert state == Subject(
        id=subject_id,
        name=SubjectName("Sample-A1"),
        status=SubjectStatus.MEASURED,
        mounted_on_asset_id=_ASSET_ID,
    )


# ---------- SubjectRemoved (Phase 4c) ----------


@pytest.mark.unit
def test_evolve_subject_removed_from_mounted_flips_status_to_removed() -> None:
    """SubjectRemoved folded onto a Mounted subject sets status=REMOVED.
    Multi-source-to-single-target: the evolver sets the same target
    status regardless of which source state preceded the event."""
    subject_id = uuid4()
    mounted = Subject(id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.MOUNTED)
    removed = evolve(mounted, SubjectRemoved(subject_id=subject_id, occurred_at=_NOW))
    assert removed == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.REMOVED
    )


@pytest.mark.unit
def test_evolve_subject_removed_from_measured_flips_status_to_removed() -> None:
    """The other source state for Removed: Measured -> Removed. Pinned
    so a future change that only handles one source state in the
    evolver is caught."""
    subject_id = uuid4()
    measured = Subject(id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.MEASURED)
    removed = evolve(measured, SubjectRemoved(subject_id=subject_id, occurred_at=_NOW))
    assert removed == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.REMOVED
    )


@pytest.mark.unit
def test_evolve_subject_removed_preserves_id_and_name() -> None:
    subject_id = uuid4()
    measured = Subject(id=subject_id, name=SubjectName("Original"), status=SubjectStatus.MEASURED)
    removed = evolve(measured, SubjectRemoved(subject_id=subject_id, occurred_at=_NOW))
    assert removed.id == subject_id
    assert removed.name == SubjectName("Original")


@pytest.mark.unit
def test_evolve_subject_removed_on_empty_state_raises() -> None:
    """SubjectRemoved before SubjectRegistered = corrupted stream."""
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, SubjectRemoved(subject_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_fold_register_mount_remove_yields_removed_subject() -> None:
    """End-to-end fold: registration + mount + remove (skipping measure)
    produces a Removed subject. Pinned because the multi-source-state
    contract has to be honored at the fold level too, not just the
    decider."""
    subject_id = uuid4()
    state = fold(
        [
            SubjectRegistered(subject_id=subject_id, name="Sample-A1", occurred_at=_NOW),
            SubjectMounted(subject_id=subject_id, asset_id=_ASSET_ID, occurred_at=_NOW),
            SubjectRemoved(subject_id=subject_id, occurred_at=_NOW),
        ]
    )
    assert state == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.REMOVED
    )


@pytest.mark.unit
def test_fold_register_mount_measure_remove_yields_removed_subject() -> None:
    """End-to-end fold: full happy path (register + mount + measure +
    remove) produces a Removed subject."""
    subject_id = uuid4()
    state = fold(
        [
            SubjectRegistered(subject_id=subject_id, name="Sample-A1", occurred_at=_NOW),
            SubjectMounted(subject_id=subject_id, asset_id=_ASSET_ID, occurred_at=_NOW),
            SubjectMeasured(subject_id=subject_id, occurred_at=_NOW),
            SubjectRemoved(subject_id=subject_id, occurred_at=_NOW),
        ]
    )
    assert state == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.REMOVED
    )


# ---------- Terminal disposition events (Phase 4d) ----------


@pytest.mark.unit
def test_evolve_subject_returned_flips_status_to_returned() -> None:
    """SubjectReturned folded onto a Removed subject sets status=RETURNED.
    Terminal disposition: same evolver pattern (event TYPE encodes
    state change), no payload field."""
    subject_id = uuid4()
    removed = Subject(id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.REMOVED)
    returned = evolve(removed, SubjectReturned(subject_id=subject_id, occurred_at=_NOW))
    assert returned == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.RETURNED
    )


@pytest.mark.unit
def test_evolve_subject_stored_flips_status_to_stored() -> None:
    subject_id = uuid4()
    removed = Subject(id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.REMOVED)
    stored = evolve(removed, SubjectStored(subject_id=subject_id, occurred_at=_NOW))
    assert stored == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.STORED
    )


@pytest.mark.unit
def test_evolve_subject_discarded_flips_status_to_discarded() -> None:
    subject_id = uuid4()
    removed = Subject(id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.REMOVED)
    discarded = evolve(
        removed,
        SubjectDiscarded(subject_id=subject_id, reason="contaminated", occurred_at=_NOW),
    )
    assert discarded == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.DISCARDED
    )


@pytest.mark.unit
def test_evolve_terminal_events_preserve_id_and_name() -> None:
    """All three terminal events only update `status`; id and name
    carry over from prior state. Pinned so a future change that
    accidentally drops the name (e.g., refactor that builds Subject
    from event fields only) is caught for all three."""
    subject_id = uuid4()
    removed = Subject(id=subject_id, name=SubjectName("Original"), status=SubjectStatus.REMOVED)
    for event in (
        SubjectReturned(subject_id=subject_id, occurred_at=_NOW),
        SubjectStored(subject_id=subject_id, occurred_at=_NOW),
        SubjectDiscarded(subject_id=subject_id, reason="contaminated", occurred_at=_NOW),
    ):
        result = evolve(removed, event)
        assert result.id == subject_id
        assert result.name == SubjectName("Original")


@pytest.mark.unit
def test_evolve_subject_returned_on_empty_state_raises() -> None:
    """Terminal events before SubjectRegistered = corrupted stream."""
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, SubjectReturned(subject_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_evolve_subject_stored_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, SubjectStored(subject_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_evolve_subject_discarded_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, SubjectDiscarded(subject_id=uuid4(), reason="contaminated", occurred_at=_NOW))


@pytest.mark.unit
def test_fold_full_lifecycle_to_returned() -> None:
    """End-to-end fold: register + mount + measure + remove + return
    produces a Returned subject. Pinned because the full lifecycle is
    the canonical happy path for one of the three terminal slices."""
    subject_id = uuid4()
    state = fold(
        [
            SubjectRegistered(subject_id=subject_id, name="Sample-A1", occurred_at=_NOW),
            SubjectMounted(subject_id=subject_id, asset_id=_ASSET_ID, occurred_at=_NOW),
            SubjectMeasured(subject_id=subject_id, occurred_at=_NOW),
            SubjectRemoved(subject_id=subject_id, occurred_at=_NOW),
            SubjectReturned(subject_id=subject_id, occurred_at=_NOW),
        ]
    )
    assert state == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.RETURNED
    )


@pytest.mark.unit
def test_fold_full_lifecycle_to_stored() -> None:
    subject_id = uuid4()
    state = fold(
        [
            SubjectRegistered(subject_id=subject_id, name="Sample-A1", occurred_at=_NOW),
            SubjectMounted(subject_id=subject_id, asset_id=_ASSET_ID, occurred_at=_NOW),
            SubjectMeasured(subject_id=subject_id, occurred_at=_NOW),
            SubjectRemoved(subject_id=subject_id, occurred_at=_NOW),
            SubjectStored(subject_id=subject_id, occurred_at=_NOW),
        ]
    )
    assert state == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.STORED
    )


@pytest.mark.unit
def test_fold_full_lifecycle_to_discarded() -> None:
    subject_id = uuid4()
    state = fold(
        [
            SubjectRegistered(subject_id=subject_id, name="Sample-A1", occurred_at=_NOW),
            SubjectMounted(subject_id=subject_id, asset_id=_ASSET_ID, occurred_at=_NOW),
            SubjectMeasured(subject_id=subject_id, occurred_at=_NOW),
            SubjectRemoved(subject_id=subject_id, occurred_at=_NOW),
            SubjectDiscarded(subject_id=subject_id, reason="contaminated", occurred_at=_NOW),
        ]
    )
    assert state == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.DISCARDED
    )
