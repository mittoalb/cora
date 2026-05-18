"""Unit tests for the `define_method` slice's pure decider."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.recipe.aggregates.method import (
    InvalidMethodNameError,
    Method,
    MethodAlreadyExistsError,
    MethodName,
)
from cora.recipe.features import define_method
from cora.recipe.features.define_method import DefineMethod

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_decide_emits_method_defined_when_stream_is_empty() -> None:
    new_id = uuid4()
    cap1 = uuid4()
    events = define_method.decide(
        state=None,
        command=DefineMethod(name="XRF Mapping", needed_families=frozenset({cap1})),
        now=_NOW,
        new_id=new_id,
    )
    assert len(events) == 1
    assert events[0].method_id == new_id
    assert events[0].name == "XRF Mapping"
    assert set(events[0].needed_families) == {cap1}
    assert events[0].occurred_at == _NOW


@pytest.mark.unit
def test_decide_trims_name_via_value_object() -> None:
    new_id = uuid4()
    events = define_method.decide(
        state=None,
        command=DefineMethod(name="  Step Tomography  ", needed_families=frozenset()),
        now=_NOW,
        new_id=new_id,
    )
    assert events[0].name == "Step Tomography"


@pytest.mark.unit
def test_decide_accepts_empty_needed_families() -> None:
    """Procedural Methods (purely operational, no Family
    requirement) are valid. Pinned because pilot use cases like
    'Sample Cleaning' might land here."""
    events = define_method.decide(
        state=None,
        command=DefineMethod(name="Sample Cleaning", needed_families=frozenset()),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].needed_families == []


@pytest.mark.unit
def test_decide_does_not_validate_capability_existence() -> None:
    """Eventual-consistency stance: decider does NOT verify the
    referenced Family ids exist in the event store. Same precedent
    as Trust Conduit zone refs (3b) and Asset parent refs (5b).
    Mismatch surfaces at Plan binding (6e)."""
    bogus_cap = UUID("01900000-0000-7000-8000-deadbeefcafe")
    events = define_method.decide(
        state=None,
        command=DefineMethod(name="X", needed_families=frozenset({bogus_cap})),
        now=_NOW,
        new_id=uuid4(),
    )
    assert set(events[0].needed_families) == {bogus_cap}


@pytest.mark.unit
def test_decide_rejects_invalid_name() -> None:
    with pytest.raises(InvalidMethodNameError):
        define_method.decide(
            state=None,
            command=DefineMethod(name="", needed_families=frozenset()),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Method(
        id=uuid4(),
        name=MethodName("XRF Mapping"),
        needed_families=frozenset(),
    )
    with pytest.raises(MethodAlreadyExistsError) as exc_info:
        define_method.decide(
            state=existing,
            command=DefineMethod(name="Other", needed_families=frozenset()),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.method_id == existing.id


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    cap1 = uuid4()
    command = DefineMethod(name="XRF Mapping", needed_families=frozenset({cap1}))
    first = define_method.decide(state=None, command=command, now=_NOW, new_id=new_id)
    second = define_method.decide(state=None, command=command, now=_NOW, new_id=new_id)
    # Compare the relevant fields (lists may be in different orders
    # since command.needed_families is a frozenset; the event's
    # list-of-UUIDs comparison via set equality below is the safe pin).
    assert len(first) == len(second) == 1
    assert first[0].method_id == second[0].method_id
    assert first[0].name == second[0].name
    assert set(first[0].needed_families) == set(second[0].needed_families)
    assert first[0].occurred_at == second[0].occurred_at


@pytest.mark.unit
def test_decide_returns_event_when_command_has_only_name() -> None:
    """Frozenset() default factory works (calling DefineMethod with
    name only produces empty needed_families). Pinned because the
    `field(default_factory=frozenset)` shape is unusual and worth
    locking."""
    events = define_method.decide(
        state=None,
        command=DefineMethod(name="X"),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].needed_families == []
