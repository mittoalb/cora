"""Unit tests for the `define_conduit` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.trust.aggregates.conduit import (
    Conduit,
    ConduitAlreadyExistsError,
    ConduitDefined,
    ConduitName,
    InvalidConduitNameError,
)
from cora.trust.features import define_conduit
from cora.trust.features.define_conduit import DefineConduit

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_decide_emits_conduit_defined_when_stream_is_empty() -> None:
    new_id = uuid4()
    source = uuid4()
    target = uuid4()
    events = define_conduit.decide(
        state=None,
        command=DefineConduit(
            name="Detector-to-Storage",
            source_zone_id=source,
            target_zone_id=target,
        ),
        now=_NOW,
        new_id=new_id,
    )
    assert events == [
        ConduitDefined(
            conduit_id=new_id,
            name="Detector-to-Storage",
            source_zone_id=source,
            target_zone_id=target,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_trims_name_via_value_object() -> None:
    events = define_conduit.decide(
        state=None,
        command=DefineConduit(
            name="  Detector-to-Storage  ",
            source_zone_id=uuid4(),
            target_zone_id=uuid4(),
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].name == "Detector-to-Storage"


@pytest.mark.unit
def test_decide_rejects_invalid_name() -> None:
    with pytest.raises(InvalidConduitNameError):
        define_conduit.decide(
            state=None,
            command=DefineConduit(
                name="",
                source_zone_id=uuid4(),
                target_zone_id=uuid4(),
            ),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Conduit(
        id=uuid4(),
        name=ConduitName("Existing"),
        source_zone_id=uuid4(),
        target_zone_id=uuid4(),
    )
    with pytest.raises(ConduitAlreadyExistsError) as exc_info:
        define_conduit.decide(
            state=existing,
            command=DefineConduit(
                name="Other",
                source_zone_id=uuid4(),
                target_zone_id=uuid4(),
            ),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.conduit_id == existing.id


@pytest.mark.unit
def test_decide_does_not_validate_zone_existence() -> None:
    """Eventual-consistency stance: the decider does NOT verify that
    `source_zone_id` / `target_zone_id` reference existing Zones.
    A typo or dangling reference produces a Conduit that points at
    nothing; downstream validation (Policy in 3c, projections later)
    catches it. This test pins the design choice so a future
    refactor that adds a load-and-verify step trips this guard."""
    events = define_conduit.decide(
        state=None,
        command=DefineConduit(
            name="Dangling",
            # Random UUIDs that have no corresponding Zone events:
            source_zone_id=uuid4(),
            target_zone_id=uuid4(),
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_allows_same_source_and_target() -> None:
    """Self-loops are not rejected at decide-time (YAGNI). If self-loops
    become a real bug class, add a `ConduitSelfLoopError` to state.py
    and raise it here; until then, permissive."""
    same = uuid4()
    events = define_conduit.decide(
        state=None,
        command=DefineConduit(
            name="Self-loop",
            source_zone_id=same,
            target_zone_id=same,
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].source_zone_id == same
    assert events[0].target_zone_id == same


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    source = uuid4()
    target = uuid4()
    command = DefineConduit(
        name="Detector-to-Storage",
        source_zone_id=source,
        target_zone_id=target,
    )
    first = define_conduit.decide(state=None, command=command, now=_NOW, new_id=new_id)
    second = define_conduit.decide(state=None, command=command, now=_NOW, new_id=new_id)
    assert first == second
