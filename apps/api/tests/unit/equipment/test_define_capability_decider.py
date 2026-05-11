"""Unit tests for the `define_capability` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.capability import (
    Capability,
    CapabilityAlreadyExistsError,
    CapabilityDefined,
    CapabilityName,
    InvalidCapabilityNameError,
)
from cora.equipment.features import define_capability
from cora.equipment.features.define_capability import DefineCapability

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_decide_emits_capability_defined_when_stream_is_empty() -> None:
    new_id = uuid4()
    events = define_capability.decide(
        state=None,
        command=DefineCapability(name="Tomography"),
        now=_NOW,
        new_id=new_id,
    )
    assert events == [CapabilityDefined(capability_id=new_id, name="Tomography", occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_trims_name_via_value_object() -> None:
    new_id = uuid4()
    events = define_capability.decide(
        state=None,
        command=DefineCapability(name="  X-ray Fluorescence  "),
        now=_NOW,
        new_id=new_id,
    )
    assert events[0].name == "X-ray Fluorescence"


@pytest.mark.unit
def test_decide_rejects_invalid_name() -> None:
    with pytest.raises(InvalidCapabilityNameError):
        define_capability.decide(
            state=None,
            command=DefineCapability(name=""),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Capability(id=uuid4(), name=CapabilityName("Tomography"))
    with pytest.raises(CapabilityAlreadyExistsError) as exc_info:
        define_capability.decide(
            state=existing,
            command=DefineCapability(name="Other"),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.capability_id == existing.id


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    command = DefineCapability(name="Tomography")
    first = define_capability.decide(state=None, command=command, now=_NOW, new_id=new_id)
    second = define_capability.decide(state=None, command=command, now=_NOW, new_id=new_id)
    assert first == second
