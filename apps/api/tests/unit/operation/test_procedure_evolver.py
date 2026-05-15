"""Procedure evolver tests (10c-a: just the genesis arm)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureName,
    ProcedureRegistered,
    ProcedureStatus,
    evolve,
    fold,
)

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_procedure_registered_sets_status_to_defined() -> None:
    procedure_id = uuid4()
    asset1 = uuid4()
    asset2 = uuid4()
    state = evolve(
        None,
        ProcedureRegistered(
            procedure_id=procedure_id,
            name="35-BM rotation-axis alignment",
            kind="alignment",
            target_asset_ids=[asset1, asset2],
            parent_run_id=None,
            occurred_at=_NOW,
        ),
    )
    assert state == Procedure(
        id=procedure_id,
        name=ProcedureName("35-BM rotation-axis alignment"),
        kind="alignment",
        target_asset_ids=frozenset({asset1, asset2}),
        status=ProcedureStatus.DEFINED,
        parent_run_id=None,
    )


@pytest.mark.unit
def test_evolve_procedure_registered_with_parent_run_id() -> None:
    procedure_id = uuid4()
    parent_run = uuid4()
    state = evolve(
        None,
        ProcedureRegistered(
            procedure_id=procedure_id,
            name="Mid-run calibration sweep",
            kind="calibration",
            target_asset_ids=[],
            parent_run_id=parent_run,
            occurred_at=_NOW,
        ),
    )
    assert state.parent_run_id == parent_run
    assert state.target_asset_ids == frozenset()


@pytest.mark.unit
def test_evolve_procedure_registered_converts_target_assets_to_frozenset() -> None:
    """target_asset_ids stored as list in payload, frozenset in state."""
    asset1 = uuid4()
    state = evolve(
        None,
        ProcedureRegistered(
            procedure_id=uuid4(),
            name="X",
            kind="bakeout",
            target_asset_ids=[asset1, asset1],  # dup
            parent_run_id=None,
            occurred_at=_NOW,
        ),
    )
    assert isinstance(state.target_asset_ids, frozenset)
    assert state.target_asset_ids == frozenset({asset1})


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_procedure_registered_returns_procedure() -> None:
    procedure_id = uuid4()
    state = fold(
        [
            ProcedureRegistered(
                procedure_id=procedure_id,
                name="X",
                kind="bakeout",
                target_asset_ids=[],
                parent_run_id=None,
                occurred_at=_NOW,
            )
        ]
    )
    assert state is not None
    assert state.id == procedure_id
    assert state.status is ProcedureStatus.DEFINED


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    events = [
        ProcedureRegistered(
            procedure_id=uuid4(),
            name="X",
            kind="bakeout",
            target_asset_ids=[],
            parent_run_id=None,
            occurred_at=_NOW,
        )
    ]
    assert fold(events) == fold(events)
