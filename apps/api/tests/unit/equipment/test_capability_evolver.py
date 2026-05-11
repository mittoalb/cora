"""Unit tests for the Capability aggregate's evolver."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.capability import (
    Capability,
    CapabilityName,
    CapabilityStatus,
    evolve,
    fold,
)
from cora.equipment.aggregates.capability.events import CapabilityDefined
from cora.equipment.features import define_capability
from cora.equipment.features.define_capability import DefineCapability

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_capability_defined_sets_status_to_defined() -> None:
    """CapabilityDefined is the genesis event; status defaults to
    Defined via the evolver. Pin so a future change (e.g. adding
    `initial_status` to the event payload) is a deliberate
    additive-state evolution."""
    capability_id = uuid4()
    state = evolve(
        None,
        CapabilityDefined(capability_id=capability_id, name="Tomography", occurred_at=_NOW),
    )
    assert state == Capability(
        id=capability_id, name=CapabilityName("Tomography"), status=CapabilityStatus.DEFINED
    )


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_capability_defined_returns_capability() -> None:
    capability_id = uuid4()
    state = fold(
        [CapabilityDefined(capability_id=capability_id, name="Tomography", occurred_at=_NOW)]
    )
    assert state == Capability(
        id=capability_id, name=CapabilityName("Tomography"), status=CapabilityStatus.DEFINED
    )


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    capability_id = uuid4()
    events = [CapabilityDefined(capability_id=capability_id, name="Tomography", occurred_at=_NOW)]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip() -> None:
    """The events the decider produces must rebuild the expected state."""
    new_id = uuid4()
    command = DefineCapability(name="  Tomography  ")  # whitespace exercises the VO trim

    events = define_capability.decide(state=None, command=command, now=_NOW, new_id=new_id)
    rebuilt = fold(events)

    assert rebuilt == Capability(
        id=new_id, name=CapabilityName("Tomography"), status=CapabilityStatus.DEFINED
    )
