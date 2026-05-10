"""Unit tests for the Zone aggregate's evolver."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.trust.aggregates.zone import Zone, ZoneName, evolve, fold
from cora.trust.aggregates.zone.events import ZoneDefined
from cora.trust.features import define_zone
from cora.trust.features.define_zone import DefineZone

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_zone_defined_from_empty_state() -> None:
    zone_id = uuid4()
    state = evolve(None, ZoneDefined(zone_id=zone_id, name="Detector", occurred_at=_NOW))
    assert state == Zone(id=zone_id, name=ZoneName("Detector"))


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_zone_defined_returns_zone() -> None:
    zone_id = uuid4()
    state = fold([ZoneDefined(zone_id=zone_id, name="Detector", occurred_at=_NOW)])
    assert state == Zone(id=zone_id, name=ZoneName("Detector"))


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    zone_id = uuid4()
    events = [ZoneDefined(zone_id=zone_id, name="Detector", occurred_at=_NOW)]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip() -> None:
    """The events the decider produces must rebuild the expected state.

    Same invariant as Access's `test_decider_and_evolver_round_trip`;
    repeated per BC because each BC's decider/evolver pair is its own
    contract.
    """
    new_id = uuid4()
    command = DefineZone(name="  Detector  ")  # whitespace exercises the VO trim

    events = define_zone.decide(state=None, command=command, now=_NOW, new_id=new_id)
    rebuilt = fold(events)

    assert rebuilt == Zone(id=new_id, name=ZoneName("Detector"))
