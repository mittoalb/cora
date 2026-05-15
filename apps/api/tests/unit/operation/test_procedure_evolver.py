"""Procedure evolver tests (10c-a genesis arm + 10c-b transition arms)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureAborted,
    ProcedureCompleted,
    ProcedureName,
    ProcedureRegistered,
    ProcedureStarted,
    ProcedureStatus,
    evolve,
    fold,
)

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _defined(
    *,
    procedure_id: UUID | None = None,
    name: str = "Vessel-A bakeout",
    kind: str = "bakeout",
    target_asset_ids: list[UUID] | None = None,
    parent_run_id: UUID | None = None,
) -> Procedure:
    """Build a Procedure in DEFINED state via fold of ProcedureRegistered."""
    state = fold(
        [
            ProcedureRegistered(
                procedure_id=procedure_id or uuid4(),
                name=name,
                kind=kind,
                target_asset_ids=target_asset_ids or [],
                parent_run_id=parent_run_id,
                occurred_at=_NOW,
            )
        ]
    )
    assert state is not None
    return state


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


# --- 10c-b transition arms ---


@pytest.mark.unit
def test_evolve_procedure_started_sets_status_to_running() -> None:
    prior = _defined()
    state = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    assert state.status is ProcedureStatus.RUNNING


@pytest.mark.unit
def test_evolve_procedure_completed_sets_status_to_completed() -> None:
    prior = _defined()
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    state = evolve(started, ProcedureCompleted(procedure_id=prior.id, occurred_at=_NOW))
    assert state.status is ProcedureStatus.COMPLETED


@pytest.mark.unit
def test_evolve_procedure_aborted_sets_status_to_aborted() -> None:
    prior = _defined()
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    state = evolve(
        started, ProcedureAborted(procedure_id=prior.id, reason="quench", occurred_at=_NOW)
    )
    assert state.status is ProcedureStatus.ABORTED


@pytest.mark.unit
def test_evolve_procedure_started_preserves_all_fields() -> None:
    """Critical invariant: transition arms must NOT silently wipe additive state.

    Mirrors the per-transition preserve-fields tests in Run BC; pinned by
    the evolver docstring's "Critical invariant" note.
    """
    asset = uuid4()
    parent_run = uuid4()
    prior = _defined(
        name="35-BM rotation-axis alignment",
        kind="alignment",
        target_asset_ids=[asset],
        parent_run_id=parent_run,
    )
    state = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    assert state.id == prior.id
    assert state.name == prior.name
    assert state.kind == "alignment"
    assert state.target_asset_ids == frozenset({asset})
    assert state.parent_run_id == parent_run


@pytest.mark.unit
def test_evolve_procedure_completed_preserves_all_fields() -> None:
    asset = uuid4()
    parent_run = uuid4()
    prior = _defined(
        name="35-BM rotation-axis alignment",
        kind="alignment",
        target_asset_ids=[asset],
        parent_run_id=parent_run,
    )
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    state = evolve(started, ProcedureCompleted(procedure_id=prior.id, occurred_at=_NOW))
    assert state.id == prior.id
    assert state.name == prior.name
    assert state.kind == "alignment"
    assert state.target_asset_ids == frozenset({asset})
    assert state.parent_run_id == parent_run


@pytest.mark.unit
def test_evolve_procedure_aborted_preserves_all_fields() -> None:
    asset = uuid4()
    prior = _defined(target_asset_ids=[asset])
    started = evolve(prior, ProcedureStarted(procedure_id=prior.id, occurred_at=_NOW))
    state = evolve(started, ProcedureAborted(procedure_id=prior.id, reason="x", occurred_at=_NOW))
    assert state.id == prior.id
    assert state.name == prior.name
    assert state.kind == prior.kind
    assert state.target_asset_ids == frozenset({asset})


@pytest.mark.unit
def test_fold_full_happy_path_yields_completed() -> None:
    pid = uuid4()
    events = [
        ProcedureRegistered(
            procedure_id=pid,
            name="X",
            kind="bakeout",
            target_asset_ids=[],
            parent_run_id=None,
            occurred_at=_NOW,
        ),
        ProcedureStarted(procedure_id=pid, occurred_at=_NOW),
        ProcedureCompleted(procedure_id=pid, occurred_at=_NOW),
    ]
    state = fold(events)
    assert state is not None
    assert state.status is ProcedureStatus.COMPLETED


@pytest.mark.unit
def test_fold_aborted_path_yields_aborted() -> None:
    pid = uuid4()
    events = [
        ProcedureRegistered(
            procedure_id=pid,
            name="X",
            kind="bakeout",
            target_asset_ids=[],
            parent_run_id=None,
            occurred_at=_NOW,
        ),
        ProcedureStarted(procedure_id=pid, occurred_at=_NOW),
        ProcedureAborted(procedure_id=pid, reason="quench", occurred_at=_NOW),
    ]
    state = fold(events)
    assert state is not None
    assert state.status is ProcedureStatus.ABORTED


@pytest.mark.unit
def test_evolve_procedure_started_on_empty_state_raises() -> None:
    """Transition events applied to None state are well-formed-stream violations."""
    with pytest.raises(ValueError, match="ProcedureStarted"):
        evolve(None, ProcedureStarted(procedure_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_evolve_procedure_completed_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="ProcedureCompleted"):
        evolve(None, ProcedureCompleted(procedure_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_evolve_procedure_aborted_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="ProcedureAborted"):
        evolve(None, ProcedureAborted(procedure_id=uuid4(), reason="x", occurred_at=_NOW))
