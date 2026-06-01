"""Unit tests for the `define_practice` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.recipe.aggregates.practice import (
    InvalidPracticeNameError,
    Practice,
    PracticeAlreadyExistsError,
    PracticeName,
)
from cora.recipe.features import define_practice
from cora.recipe.features.define_practice import DefinePractice

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_decide_emits_practice_defined_when_stream_is_empty() -> None:
    new_id = uuid4()
    method_id = uuid4()
    site_id = uuid4()
    events = define_practice.decide(
        state=None,
        command=DefinePractice(
            name="APS Standard Tomography",
            method_id=method_id,
            site_id=site_id,
        ),
        now=_NOW,
        new_id=new_id,
    )
    assert len(events) == 1
    assert events[0].practice_id == new_id
    assert events[0].name == "APS Standard Tomography"
    assert events[0].method_id == method_id
    assert events[0].site_id == site_id
    assert events[0].occurred_at == _NOW


@pytest.mark.unit
def test_decide_trims_name_via_value_object() -> None:
    new_id = uuid4()
    events = define_practice.decide(
        state=None,
        command=DefinePractice(
            name="  APS XRF Fly Mapping  ",
            method_id=uuid4(),
            site_id=uuid4(),
        ),
        now=_NOW,
        new_id=new_id,
    )
    assert events[0].name == "APS XRF Fly Mapping"


@pytest.mark.unit
def test_decide_does_not_validate_method_or_site_existence() -> None:
    """Eventual-consistency stance: decider does NOT verify that
    method_id or site_id refer to real aggregate streams. Same
    precedent as Conduit zone refs (3b), Method.needed_family_ids
    (6a), Asset.families entries (5f-1)."""
    bogus_method = uuid4()
    bogus_site = uuid4()
    events = define_practice.decide(
        state=None,
        command=DefinePractice(name="X", method_id=bogus_method, site_id=bogus_site),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].method_id == bogus_method
    assert events[0].site_id == bogus_site


@pytest.mark.unit
def test_decide_rejects_invalid_name() -> None:
    with pytest.raises(InvalidPracticeNameError):
        define_practice.decide(
            state=None,
            command=DefinePractice(name="", method_id=uuid4(), site_id=uuid4()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Practice(
        id=uuid4(),
        name=PracticeName("X"),
        method_id=uuid4(),
        site_id=uuid4(),
    )
    with pytest.raises(PracticeAlreadyExistsError) as exc_info:
        define_practice.decide(
            state=existing,
            command=DefinePractice(name="Other", method_id=uuid4(), site_id=uuid4()),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.practice_id == existing.id


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    command = DefinePractice(name="X", method_id=uuid4(), site_id=uuid4())
    first = define_practice.decide(state=None, command=command, now=_NOW, new_id=new_id)
    second = define_practice.decide(state=None, command=command, now=_NOW, new_id=new_id)
    assert first == second
