"""Unit tests for the Method aggregate's evolver.

Pinned: list[UUID] in event payload converts to frozenset[UUID] in
state (set semantics for Plan-binding superset checks).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.recipe.aggregates.method import (
    Method,
    MethodName,
    MethodStatus,
    evolve,
    fold,
)
from cora.recipe.aggregates.method.events import MethodDefined
from cora.recipe.features import define_method
from cora.recipe.features.define_method import DefineMethod

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_method_defined_sets_status_to_defined() -> None:
    """MethodDefined is the genesis event; status defaults to Defined
    via the evolver. Pin so a future change (e.g. adding
    `initial_status` to the event payload) is a deliberate
    additive-state evolution."""
    method_id = uuid4()
    cap1 = uuid4()
    state = evolve(
        None,
        MethodDefined(
            method_id=method_id,
            name="XRF Fly Mapping",
            needs_capabilities=[cap1],
            occurred_at=_NOW,
        ),
    )
    assert state == Method(
        id=method_id,
        name=MethodName("XRF Fly Mapping"),
        needs_capabilities=frozenset({cap1}),
        status=MethodStatus.DEFINED,
    )


@pytest.mark.unit
def test_evolve_converts_list_to_frozenset() -> None:
    """Event payload carries `list[UUID]` (JSON-friendly); state
    holds `frozenset[UUID]` (set semantics for Plan-binding
    superset checks). Locked because a future refactor that
    drops the conversion would silently break Plan-time set
    operations."""
    cap1 = uuid4()
    cap2 = uuid4()
    cap3 = uuid4()
    state = evolve(
        None,
        MethodDefined(
            method_id=uuid4(),
            name="X",
            needs_capabilities=[cap1, cap2, cap3, cap1],  # duplicate
            occurred_at=_NOW,
        ),
    )
    assert state.needs_capabilities == frozenset({cap1, cap2, cap3})
    assert isinstance(state.needs_capabilities, frozenset)


@pytest.mark.unit
def test_evolve_handles_empty_needs_capabilities() -> None:
    """Procedural Methods (no equipment requirement) fold to empty
    frozenset; Plan-binding's superset check still works
    (frozenset() ⊆ anything)."""
    state = evolve(
        None,
        MethodDefined(
            method_id=uuid4(),
            name="Sample Cleaning",
            needs_capabilities=[],
            occurred_at=_NOW,
        ),
    )
    assert state.needs_capabilities == frozenset()


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_method_defined_returns_method() -> None:
    method_id = uuid4()
    cap1 = uuid4()
    state = fold(
        [
            MethodDefined(
                method_id=method_id,
                name="Step Tomography",
                needs_capabilities=[cap1],
                occurred_at=_NOW,
            )
        ]
    )
    assert state == Method(
        id=method_id,
        name=MethodName("Step Tomography"),
        needs_capabilities=frozenset({cap1}),
        status=MethodStatus.DEFINED,
    )


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    cap1 = uuid4()
    events = [
        MethodDefined(
            method_id=uuid4(),
            name="X",
            needs_capabilities=[cap1],
            occurred_at=_NOW,
        )
    ]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip() -> None:
    """End-to-end: decider produces events that the evolver folds back
    to the expected state."""
    new_id = uuid4()
    cap1 = UUID("01900000-0000-7000-8000-000000000111")
    cap2 = UUID("01900000-0000-7000-8000-000000000222")
    command = DefineMethod(
        name="  XRF Fly Mapping  ",
        needs_capabilities=frozenset({cap1, cap2}),
    )
    events = define_method.decide(state=None, command=command, now=_NOW, new_id=new_id)
    rebuilt = fold(events)
    assert rebuilt == Method(
        id=new_id,
        name=MethodName("XRF Fly Mapping"),
        needs_capabilities=frozenset({cap1, cap2}),
        status=MethodStatus.DEFINED,
    )
