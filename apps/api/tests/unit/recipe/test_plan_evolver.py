"""Unit tests for the Plan aggregate's evolver."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.recipe.aggregates.plan import (
    Plan,
    PlanName,
    PlanStatus,
    evolve,
    fold,
)
from cora.recipe.aggregates.plan.events import PlanDefined

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _plan_defined(
    *,
    plan_id: UUID | None = None,
    practice_id: UUID | None = None,
    asset_ids: list[UUID] | None = None,
) -> PlanDefined:
    """Test helper: PlanDefined with sensible defaults for non-relevant fields."""
    return PlanDefined(
        plan_id=plan_id or uuid4(),
        name="32-ID FlyScan",
        practice_id=practice_id or uuid4(),
        asset_ids=asset_ids if asset_ids is not None else [uuid4()],
        method_id=uuid4(),
        method_needs_capabilities_snapshot=[uuid4()],
        asset_capabilities_snapshot={},
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_evolve_plan_defined_sets_status_to_defined() -> None:
    """PlanDefined is the genesis event; status defaults to Defined
    via the evolver. Audit snapshots in payload are NOT folded into
    state (gate-review Q4: slim aggregate)."""
    plan_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    state = evolve(
        None,
        PlanDefined(
            plan_id=plan_id,
            name="32-ID FlyScan",
            practice_id=practice_id,
            asset_ids=[asset_id],
            method_id=uuid4(),
            method_needs_capabilities_snapshot=[uuid4()],
            asset_capabilities_snapshot={asset_id: [uuid4()]},
            occurred_at=_NOW,
        ),
    )
    assert state == Plan(
        id=plan_id,
        name=PlanName("32-ID FlyScan"),
        practice_id=practice_id,
        asset_ids=frozenset({asset_id}),
        status=PlanStatus.DEFINED,
    )


@pytest.mark.unit
def test_evolve_plan_defined_converts_asset_ids_list_to_frozenset() -> None:
    """Event payload carries `list[UUID]` (JSON-friendly); state
    holds `frozenset[UUID]` (set semantics for membership). Same
    precedent as Method's needs_capabilities."""
    a1 = uuid4()
    a2 = uuid4()
    state = evolve(None, _plan_defined(asset_ids=[a1, a2, a1]))  # duplicate
    assert state.asset_ids == frozenset({a1, a2})
    assert isinstance(state.asset_ids, frozenset)


@pytest.mark.unit
def test_evolve_plan_defined_does_not_fold_audit_snapshots() -> None:
    """Slim aggregate: snapshots in payload are NOT folded into
    state. Plan state has no method_id, method_needs_capabilities,
    or asset_capabilities fields. This test pins that future
    additions don't accidentally widen state."""
    state = evolve(None, _plan_defined())
    # Plan dataclass field set is the contract.
    assert {f for f in state.__dataclass_fields__} == {
        "id",
        "name",
        "practice_id",
        "asset_ids",
        "status",
    }


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_plan_defined_returns_plan() -> None:
    plan_id = uuid4()
    state = fold([_plan_defined(plan_id=plan_id)])
    assert state is not None
    assert state.id == plan_id
    assert state.status is PlanStatus.DEFINED


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    events = [_plan_defined()]
    assert fold(events) == fold(events)
