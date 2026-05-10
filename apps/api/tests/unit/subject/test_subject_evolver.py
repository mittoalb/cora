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
from cora.subject.aggregates.subject.events import SubjectRegistered
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
