"""Unit tests for the `register_subject` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.subject.aggregates.subject import (
    InvalidSubjectNameError,
    Subject,
    SubjectAlreadyExistsError,
    SubjectName,
    SubjectRegistered,
)
from cora.subject.features import register_subject
from cora.subject.features.register_subject import RegisterSubject

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_decide_emits_subject_registered_when_stream_is_empty() -> None:
    new_id = uuid4()
    events = register_subject.decide(
        state=None,
        command=RegisterSubject(name="Sample-A1"),
        now=_NOW,
        new_id=new_id,
    )
    assert events == [SubjectRegistered(subject_id=new_id, name="Sample-A1", occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_trims_name_via_value_object() -> None:
    new_id = uuid4()
    events = register_subject.decide(
        state=None,
        command=RegisterSubject(name="  Sample-A1  "),
        now=_NOW,
        new_id=new_id,
    )
    assert events[0].name == "Sample-A1"


@pytest.mark.unit
def test_decide_rejects_invalid_name() -> None:
    with pytest.raises(InvalidSubjectNameError):
        register_subject.decide(
            state=None,
            command=RegisterSubject(name=""),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Subject(id=uuid4(), name=SubjectName("Sample-A1"))
    with pytest.raises(SubjectAlreadyExistsError) as exc_info:
        register_subject.decide(
            state=existing,
            command=RegisterSubject(name="Other"),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.subject_id == existing.id


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    command = RegisterSubject(name="Sample-A1")
    first = register_subject.decide(state=None, command=command, now=_NOW, new_id=new_id)
    second = register_subject.decide(state=None, command=command, now=_NOW, new_id=new_id)
    assert first == second
