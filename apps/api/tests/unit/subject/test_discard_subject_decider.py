"""Unit tests for the `discard_subject` slice's pure decider.

Terminal disposition: `Removed -> Discarded`. Single-source guard.
Mirrors `return_subject` / `store_subject` decider tests.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotDiscardError,
    SubjectDiscarded,
    SubjectName,
    SubjectNotFoundError,
    SubjectStatus,
)
from cora.subject.features import discard_subject
from cora.subject.features.discard_subject import DiscardSubject

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _subject(*, status: SubjectStatus = SubjectStatus.REMOVED) -> Subject:
    return Subject(id=uuid4(), name=SubjectName("Sample-A1"), status=status)


@pytest.mark.unit
def test_decide_emits_subject_discarded_when_state_is_removed() -> None:
    state = _subject(status=SubjectStatus.REMOVED)
    events = discard_subject.decide(
        state=state,
        command=DiscardSubject(subject_id=state.id),
        now=_NOW,
    )
    assert events == [SubjectDiscarded(subject_id=state.id, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_subject_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(SubjectNotFoundError) as exc_info:
        discard_subject.decide(
            state=None,
            command=DiscardSubject(subject_id=target_id),
            now=_NOW,
        )
    assert exc_info.value.subject_id == target_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "current",
    [
        SubjectStatus.RECEIVED,
        SubjectStatus.MOUNTED,
        SubjectStatus.MEASURED,
        SubjectStatus.RETURNED,
        SubjectStatus.STORED,
        SubjectStatus.DISCARDED,
    ],
)
def test_decide_raises_cannot_discard_for_every_non_removed_state(
    current: SubjectStatus,
) -> None:
    """Strict semantics, not idempotent: re-discarding an already-
    `Discarded` subject also raises. All six wrong states tested
    explicitly."""
    state = _subject(status=current)
    with pytest.raises(SubjectCannotDiscardError) as exc_info:
        discard_subject.decide(
            state=state,
            command=DiscardSubject(subject_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.subject_id == state.id
    assert exc_info.value.current_status is current


@pytest.mark.unit
def test_decide_error_carries_current_status_for_diagnostic_messaging() -> None:
    state = _subject(status=SubjectStatus.RECEIVED)
    with pytest.raises(SubjectCannotDiscardError) as exc_info:
        discard_subject.decide(
            state=state,
            command=DiscardSubject(subject_id=state.id),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Received" in msg
    assert "Removed" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _subject(status=SubjectStatus.REMOVED)
    command = DiscardSubject(subject_id=state.id)
    first = discard_subject.decide(state=state, command=command, now=_NOW)
    second = discard_subject.decide(state=state, command=command, now=_NOW)
    assert first == second
