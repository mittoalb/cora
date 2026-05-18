"""Unit tests for the `define_family` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.family import (
    Family,
    FamilyAlreadyExistsError,
    FamilyDefined,
    FamilyName,
    InvalidFamilyNameError,
)
from cora.equipment.features import define_family
from cora.equipment.features.define_family import DefineFamily

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_decide_emits_capability_defined_when_stream_is_empty() -> None:
    new_id = uuid4()
    events = define_family.decide(
        state=None,
        command=DefineFamily(name="Tomography", affordances=frozenset()),
        now=_NOW,
        new_id=new_id,
    )
    assert events == [FamilyDefined(family_id=new_id, name="Tomography", occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_trims_name_via_value_object() -> None:
    new_id = uuid4()
    events = define_family.decide(
        state=None,
        command=DefineFamily(name="  X-ray Fluorescence  ", affordances=frozenset()),
        now=_NOW,
        new_id=new_id,
    )
    assert events[0].name == "X-ray Fluorescence"


@pytest.mark.unit
def test_decide_rejects_invalid_name() -> None:
    with pytest.raises(InvalidFamilyNameError):
        define_family.decide(
            state=None,
            command=DefineFamily(name="", affordances=frozenset()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Family(id=uuid4(), name=FamilyName("Tomography"))
    with pytest.raises(FamilyAlreadyExistsError) as exc_info:
        define_family.decide(
            state=existing,
            command=DefineFamily(name="Other", affordances=frozenset()),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.family_id == existing.id


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    command = DefineFamily(name="Tomography", affordances=frozenset())
    first = define_family.decide(state=None, command=command, now=_NOW, new_id=new_id)
    second = define_family.decide(state=None, command=command, now=_NOW, new_id=new_id)
    assert first == second
