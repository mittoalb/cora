"""Unit tests for the `remove_plan_wire` slice's pure decider (Phase 6h).

Mirror of add_plan_wire's decider tests; remove only needs:
  - PlanNotFoundError on empty state
  - InvalidWireError on malformed port name
  - PlanWireNotFoundError on absent wire (strict-not-idempotent)
  - Happy path: emits PlanWireRemoved with full 4-tuple

No cross-aggregate context; remove is a pure set-difference operation.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.recipe.aggregates.plan import (
    InvalidWireError,
    Plan,
    PlanName,
    PlanNotFoundError,
    PlanStatus,
    PlanWireNotFoundError,
    PlanWireRemoved,
    Wire,
)
from cora.recipe.features import remove_plan_wire
from cora.recipe.features.remove_plan_wire import RemovePlanWire

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


def _plan(*, wires: frozenset[Wire] = frozenset()) -> Plan:
    return Plan(
        id=uuid4(),
        name=PlanName("32-ID FlyScan"),
        practice_id=uuid4(),
        asset_ids=frozenset({uuid4()}),
        status=PlanStatus.DEFINED,
        method_id=uuid4(),
        wires=wires,
    )


@pytest.mark.unit
def test_decide_raises_plan_not_found_on_empty_state() -> None:
    plan_id = uuid4()
    with pytest.raises(PlanNotFoundError):
        remove_plan_wire.decide(
            state=None,
            command=RemovePlanWire(
                plan_id=plan_id,
                source_asset_id=uuid4(),
                source_port_name="trigger_out",
                target_asset_id=uuid4(),
                target_port_name="trigger_in",
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_invalid_wire_on_empty_port_name() -> None:
    state = _plan()
    with pytest.raises(InvalidWireError):
        remove_plan_wire.decide(
            state=state,
            command=RemovePlanWire(
                plan_id=state.id,
                source_asset_id=uuid4(),
                source_port_name="trigger_out",
                target_asset_id=uuid4(),
                target_port_name="   ",  # empty after trim
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_wire_not_found_on_absent_wire() -> None:
    """Strict-not-idempotent: removing a wire that's not in the set raises."""
    state = _plan(wires=frozenset())
    with pytest.raises(PlanWireNotFoundError):
        remove_plan_wire.decide(
            state=state,
            command=RemovePlanWire(
                plan_id=state.id,
                source_asset_id=uuid4(),
                source_port_name="trigger_out",
                target_asset_id=uuid4(),
                target_port_name="trigger_in",
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_emits_event_on_happy_path() -> None:
    src_id = uuid4()
    tgt_id = uuid4()
    existing = Wire(
        source_asset_id=src_id,
        source_port_name="trigger_out",
        target_asset_id=tgt_id,
        target_port_name="trigger_in",
    )
    state = _plan(wires=frozenset({existing}))
    events = remove_plan_wire.decide(
        state=state,
        command=RemovePlanWire(
            plan_id=state.id,
            source_asset_id=src_id,
            source_port_name="trigger_out",
            target_asset_id=tgt_id,
            target_port_name="trigger_in",
        ),
        now=_NOW,
    )
    assert events == [
        PlanWireRemoved(
            plan_id=state.id,
            source_asset_id=src_id,
            source_port_name="trigger_out",
            target_asset_id=tgt_id,
            target_port_name="trigger_in",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_does_not_require_assets_or_ports_to_exist() -> None:
    """Hot-swap: wire-removal works even if Asset.ports have changed
    since the wire was added (no cross-aggregate validation on remove)."""
    src_id = uuid4()
    tgt_id = uuid4()
    existing = Wire(
        source_asset_id=src_id,
        source_port_name="trigger_out",
        target_asset_id=tgt_id,
        target_port_name="trigger_in",
    )
    # Note: state.asset_ids does NOT include src_id or tgt_id; the wire
    # was added before they were removed. Remove should still succeed.
    state = Plan(
        id=uuid4(),
        name=PlanName("Plan"),
        practice_id=uuid4(),
        asset_ids=frozenset({uuid4()}),  # different asset
        status=PlanStatus.DEFINED,
        method_id=uuid4(),
        wires=frozenset({existing}),
    )
    events = remove_plan_wire.decide(
        state=state,
        command=RemovePlanWire(
            plan_id=state.id,
            source_asset_id=src_id,
            source_port_name="trigger_out",
            target_asset_id=tgt_id,
            target_port_name="trigger_in",
        ),
        now=_NOW,
    )
    assert len(events) == 1
