"""Unit tests for the Subject aggregate's evolver."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.subject.aggregates.subject import (
    Subject,
    SubjectName,
    SubjectStatus,
    evolve,
    fold,
)
from cora.subject.aggregates.subject.events import SubjectMounted, SubjectRegistered
from cora.subject.features import register_subject
from cora.subject.features.register_subject import RegisterSubject

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


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
    mounted = evolve(received, SubjectMounted(subject_id=subject_id, occurred_at=_NOW))
    assert mounted == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.MOUNTED
    )


@pytest.mark.unit
def test_evolve_subject_mounted_preserves_id_and_name() -> None:
    """The evolver only updates `status`; id and name are carried over
    from prior state. Pinned so a future change that accidentally
    drops the name (e.g., refactor that builds Subject from event
    fields only) is caught."""
    subject_id = uuid4()
    received = Subject(id=subject_id, name=SubjectName("Original"), status=SubjectStatus.RECEIVED)
    mounted = evolve(received, SubjectMounted(subject_id=subject_id, occurred_at=_NOW))
    assert mounted.id == subject_id
    assert mounted.name == SubjectName("Original")


@pytest.mark.unit
def test_evolve_subject_mounted_on_empty_state_raises() -> None:
    """SubjectMounted before SubjectRegistered = corrupted stream.
    Fail loud rather than silently producing an empty subject."""
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, SubjectMounted(subject_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_fold_register_then_mount_yields_mounted_subject() -> None:
    """End-to-end fold: registration + mount produces a Mounted subject."""
    subject_id = uuid4()
    state = fold(
        [
            SubjectRegistered(subject_id=subject_id, name="Sample-A1", occurred_at=_NOW),
            SubjectMounted(subject_id=subject_id, occurred_at=_NOW),
        ]
    )
    assert state == Subject(
        id=subject_id, name=SubjectName("Sample-A1"), status=SubjectStatus.MOUNTED
    )
