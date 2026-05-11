"""Unit tests for the Practice aggregate's evolver."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.recipe.aggregates.practice import (
    Practice,
    PracticeName,
    PracticeStatus,
    evolve,
    fold,
)
from cora.recipe.aggregates.practice.events import PracticeDefined
from cora.recipe.features import define_practice
from cora.recipe.features.define_practice import DefinePractice

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_practice_defined_sets_status_to_defined() -> None:
    """PracticeDefined is the genesis event; status defaults to
    Defined via the evolver. current_version starts None."""
    practice_id = uuid4()
    method_id = uuid4()
    site_id = uuid4()
    state = evolve(
        None,
        PracticeDefined(
            practice_id=practice_id,
            name="APS Standard Tomography",
            method_id=method_id,
            site_id=site_id,
            occurred_at=_NOW,
        ),
    )
    assert state == Practice(
        id=practice_id,
        name=PracticeName("APS Standard Tomography"),
        method_id=method_id,
        site_id=site_id,
        status=PracticeStatus.DEFINED,
    )
    assert state.current_version is None


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_practice_defined_returns_practice() -> None:
    practice_id = uuid4()
    method_id = uuid4()
    site_id = uuid4()
    state = fold(
        [
            PracticeDefined(
                practice_id=practice_id,
                name="APS Sector 2 XRF",
                method_id=method_id,
                site_id=site_id,
                occurred_at=_NOW,
            )
        ]
    )
    assert state == Practice(
        id=practice_id,
        name=PracticeName("APS Sector 2 XRF"),
        method_id=method_id,
        site_id=site_id,
        status=PracticeStatus.DEFINED,
    )


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    practice_id = uuid4()
    events = [
        PracticeDefined(
            practice_id=practice_id,
            name="X",
            method_id=uuid4(),
            site_id=uuid4(),
            occurred_at=_NOW,
        )
    ]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip() -> None:
    """End-to-end: decider produces events that the evolver folds back."""
    new_id = uuid4()
    method_id = uuid4()
    site_id = uuid4()
    command = DefinePractice(
        name="  APS Standard Tomography  ",  # whitespace exercises VO trim
        method_id=method_id,
        site_id=site_id,
    )
    events = define_practice.decide(state=None, command=command, now=_NOW, new_id=new_id)
    rebuilt = fold(events)
    assert rebuilt == Practice(
        id=new_id,
        name=PracticeName("APS Standard Tomography"),
        method_id=method_id,
        site_id=site_id,
        status=PracticeStatus.DEFINED,
    )
