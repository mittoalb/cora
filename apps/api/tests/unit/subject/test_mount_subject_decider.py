"""Unit tests for the `mount_subject` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotMountError,
    SubjectMounted,
    SubjectName,
    SubjectNotFoundError,
    SubjectStatus,
)
from cora.subject.features import mount_subject
from cora.subject.features.mount_subject import MountSubject

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _subject(*, status: SubjectStatus = SubjectStatus.RECEIVED) -> Subject:
    return Subject(id=uuid4(), name=SubjectName("Sample-A1"), status=status)


@pytest.mark.unit
def test_decide_emits_subject_mounted_when_state_is_received() -> None:
    state = _subject(status=SubjectStatus.RECEIVED)
    events = mount_subject.decide(
        state=state,
        command=MountSubject(subject_id=state.id),
        now=_NOW,
    )
    assert events == [SubjectMounted(subject_id=state.id, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_subject_not_found_when_state_is_none() -> None:
    """Update-style precondition: state must exist."""
    target_id = uuid4()
    with pytest.raises(SubjectNotFoundError) as exc_info:
        mount_subject.decide(
            state=None,
            command=MountSubject(subject_id=target_id),
            now=_NOW,
        )
    assert exc_info.value.subject_id == target_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "current",
    [
        SubjectStatus.MOUNTED,
        SubjectStatus.MEASURED,
        SubjectStatus.REMOVED,
        SubjectStatus.RETURNED,
        SubjectStatus.STORED,
        SubjectStatus.DISCARDED,
    ],
)
def test_decide_raises_cannot_mount_for_every_non_received_state(
    current: SubjectStatus,
) -> None:
    """Strict semantics, not idempotent: mounting an already-mounted (or
    otherwise non-Received) subject raises. Six wrong states tested
    explicitly so a future relaxation has to flip every parametrized
    case deliberately."""
    state = _subject(status=current)
    with pytest.raises(SubjectCannotMountError) as exc_info:
        mount_subject.decide(
            state=state,
            command=MountSubject(subject_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.subject_id == state.id
    assert exc_info.value.current_status is current


@pytest.mark.unit
def test_decide_error_carries_current_status_for_diagnostic_messaging() -> None:
    """The error message includes both the current state and the
    expected source state — pinned because the route's 409 body
    surfaces this string."""
    state = _subject(status=SubjectStatus.MEASURED)
    with pytest.raises(SubjectCannotMountError) as exc_info:
        mount_subject.decide(
            state=state,
            command=MountSubject(subject_id=state.id),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Measured" in msg
    assert "Received" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _subject(status=SubjectStatus.RECEIVED)
    command = MountSubject(subject_id=state.id)
    first = mount_subject.decide(state=state, command=command, now=_NOW)
    second = mount_subject.decide(state=state, command=command, now=_NOW)
    assert first == second
