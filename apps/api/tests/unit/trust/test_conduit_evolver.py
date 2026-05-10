"""Unit tests for the Conduit aggregate's evolver."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.trust.aggregates.conduit import Conduit, ConduitName, evolve, fold
from cora.trust.aggregates.conduit.events import ConduitDefined
from cora.trust.features import define_conduit
from cora.trust.features.define_conduit import DefineConduit

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_conduit_defined_from_empty_state() -> None:
    conduit_id = uuid4()
    source = uuid4()
    target = uuid4()
    state = evolve(
        None,
        ConduitDefined(
            conduit_id=conduit_id,
            name="Detector-to-Storage",
            source_zone_id=source,
            target_zone_id=target,
            occurred_at=_NOW,
        ),
    )
    assert state == Conduit(
        id=conduit_id,
        name=ConduitName("Detector-to-Storage"),
        source_zone_id=source,
        target_zone_id=target,
    )


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_conduit_defined_returns_conduit() -> None:
    conduit_id = uuid4()
    source = uuid4()
    target = uuid4()
    state = fold(
        [
            ConduitDefined(
                conduit_id=conduit_id,
                name="Detector-to-Storage",
                source_zone_id=source,
                target_zone_id=target,
                occurred_at=_NOW,
            )
        ]
    )
    assert state == Conduit(
        id=conduit_id,
        name=ConduitName("Detector-to-Storage"),
        source_zone_id=source,
        target_zone_id=target,
    )


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    conduit_id = uuid4()
    events = [
        ConduitDefined(
            conduit_id=conduit_id,
            name="Detector-to-Storage",
            source_zone_id=uuid4(),
            target_zone_id=uuid4(),
            occurred_at=_NOW,
        )
    ]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip() -> None:
    """The events the decider produces must rebuild the expected state."""
    new_id = uuid4()
    source = uuid4()
    target = uuid4()
    command = DefineConduit(
        name="  Detector-to-Storage  ",  # whitespace exercises the VO trim
        source_zone_id=source,
        target_zone_id=target,
    )

    events = define_conduit.decide(state=None, command=command, now=_NOW, new_id=new_id)
    rebuilt = fold(events)

    assert rebuilt == Conduit(
        id=new_id,
        name=ConduitName("Detector-to-Storage"),
        source_zone_id=source,
        target_zone_id=target,
    )
