"""Unit tests for the `define_zone` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.trust.aggregates.zone import (
    InvalidZoneNameError,
    Zone,
    ZoneAlreadyExistsError,
    ZoneDefined,
    ZoneName,
)
from cora.trust.features import define_zone
from cora.trust.features.define_zone import DefineZone

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_decide_emits_zone_defined_when_stream_is_empty() -> None:
    new_id = uuid4()
    events = define_zone.decide(
        state=None,
        command=DefineZone(name="Detector"),
        now=_NOW,
        new_id=new_id,
    )
    assert events == [ZoneDefined(zone_id=new_id, name="Detector", occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_trims_name_via_value_object() -> None:
    new_id = uuid4()
    events = define_zone.decide(
        state=None,
        command=DefineZone(name="  Detector  "),
        now=_NOW,
        new_id=new_id,
    )
    assert events[0].name == "Detector"


@pytest.mark.unit
def test_decide_rejects_invalid_name() -> None:
    with pytest.raises(InvalidZoneNameError):
        define_zone.decide(
            state=None,
            command=DefineZone(name=""),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Zone(id=uuid4(), name=ZoneName("Detector"))
    with pytest.raises(ZoneAlreadyExistsError) as exc_info:
        define_zone.decide(
            state=existing,
            command=DefineZone(name="Other"),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.zone_id == existing.id


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    command = DefineZone(name="Detector")
    first = define_zone.decide(state=None, command=command, now=_NOW, new_id=new_id)
    second = define_zone.decide(state=None, command=command, now=_NOW, new_id=new_id)
    assert first == second
