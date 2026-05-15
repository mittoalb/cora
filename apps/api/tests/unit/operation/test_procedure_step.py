"""ProcedureStep dataclass + InMemoryStepStore tests.

Mirrors `test_run_reading.py` shape (per-category writer port).
PostgresStepStore lives in integration tests; in-memory adapter is
tested here for shape + dedup semantics.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.operation.aggregates.procedure import (
    InMemoryStepStore,
    ProcedureStep,
)

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _row(
    *,
    event_id: UUID | None = None,
    step_kind: str = "setpoint",
    payload: dict[str, object] | None = None,
) -> ProcedureStep:
    return ProcedureStep(
        event_id=event_id or uuid4(),
        procedure_id=uuid4(),
        logbook_id=uuid4(),
        actor_id=uuid4(),
        command_name="AppendProcedureStep",
        step_kind=step_kind,
        payload=payload or {"channel": "T_oven", "target_value": 423.0},
        sampled_at=_NOW,
        occurred_at=_NOW,
        correlation_id=uuid4(),
        causation_id=None,
    )


@pytest.mark.unit
def test_procedure_step_is_a_frozen_dataclass() -> None:
    row = _row()
    with pytest.raises(Exception):  # noqa: B017  # dataclass FrozenInstanceError
        row.step_kind = "action"  # type: ignore[misc]


@pytest.mark.unit
def test_procedure_step_carries_polymorphic_payload_for_setpoint() -> None:
    row = _row(
        step_kind="setpoint",
        payload={"channel": "T_oven", "target_value": 423.0, "units": "K"},
    )
    assert row.step_kind == "setpoint"
    assert row.payload["channel"] == "T_oven"
    assert row.payload["target_value"] == 423.0


@pytest.mark.unit
def test_procedure_step_carries_polymorphic_payload_for_action() -> None:
    row = _row(
        step_kind="action",
        payload={"action_name": "open_valve", "params": {"valve": "V12"}},
    )
    assert row.step_kind == "action"
    assert row.payload["action_name"] == "open_valve"


@pytest.mark.unit
def test_procedure_step_carries_polymorphic_payload_for_check() -> None:
    row = _row(
        step_kind="check",
        payload={"channel": "T_oven", "passed": True, "expected": 423.0, "actual": 422.8},
    )
    assert row.step_kind == "check"
    assert row.payload["passed"] is True


# ---------- InMemoryStepStore ----------


@pytest.mark.unit
async def test_inmemory_step_store_appends_single_row() -> None:
    store = InMemoryStepStore()
    row = _row()
    await store.append([row])
    assert store.all() == [row]


@pytest.mark.unit
async def test_inmemory_step_store_appends_batch() -> None:
    store = InMemoryStepStore()
    rows = [_row() for _ in range(5)]
    await store.append(rows)
    # Order is insertion order via setdefault.
    assert {r.event_id for r in store.all()} == {r.event_id for r in rows}


@pytest.mark.unit
async def test_inmemory_step_store_dedups_by_event_id() -> None:
    """ON CONFLICT (event_id) DO NOTHING semantics: existing wins."""
    store = InMemoryStepStore()
    eid = uuid4()
    first = _row(event_id=eid, step_kind="setpoint")
    second = _row(event_id=eid, step_kind="action")  # same id, different body
    await store.append([first])
    await store.append([second])
    assert len(store.all()) == 1
    assert store.all()[0].step_kind == "setpoint"  # first wins


@pytest.mark.unit
async def test_inmemory_step_store_handles_empty_batch() -> None:
    store = InMemoryStepStore()
    await store.append([])
    assert store.all() == []


@pytest.mark.unit
async def test_inmemory_step_store_preserves_distinct_event_ids() -> None:
    store = InMemoryStepStore()
    rows = [_row() for _ in range(3)]
    await store.append(rows)
    assert len({r.event_id for r in store.all()}) == 3
