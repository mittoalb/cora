"""Application-handler tests for `append_procedure_step` slice.

Lazy open-on-first-write + batch append. Mirrors
`test_append_run_reading_handler.py` shape (which mirrors 8c-b's
`test_append_reasoning_entry_handler.py`).

Tests seed a Procedure in `Running` state directly into the in-memory
event store via `to_new_event` + `event_store.append`, then exercise
the handler with an InMemoryStepStore.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.operation.aggregates.procedure import (
    InMemoryStepStore,
    InvalidStepKindError,
    ProcedureNotFoundError,
    ProcedureRegistered,
    ProcedureStarted,
    ProcedureStepsLogbookClosedError,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features import append_procedure_step
from cora.operation.features.append_procedure_step import (
    AppendProcedureSteps,
    ProcedureStepInput,
)
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 5, 15, 11, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000c0e01")
_LOGBOOK_ID = UUID("01900000-0000-7000-8000-0000000c0e02")
_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c0e03")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_running_procedure(store: InMemoryEventStore) -> None:
    """Append Registered + Started events for a Running Procedure."""
    registered = ProcedureRegistered(
        procedure_id=_PROCEDURE_ID,
        name="Vessel-A bakeout",
        kind="bakeout",
        target_asset_ids=[],
        parent_run_id=None,
        occurred_at=_PRIOR,
    )
    started = ProcedureStarted(procedure_id=_PROCEDURE_ID, occurred_at=_PRIOR)
    for index, event in enumerate((registered, started)):
        new_event = to_new_event(
            event_type=event_type_name(event),
            payload=to_payload(event),
            occurred_at=event.occurred_at,
            event_id=uuid4(),
            command_name="RegisterProcedure" if index == 0 else "StartProcedure",
            correlation_id=_CORRELATION_ID,
            principal_id=_PRINCIPAL_ID,
        )
        await store.append(
            stream_type="Procedure",
            stream_id=_PROCEDURE_ID,
            expected_version=index,
            events=[new_event],
        )


async def _seed_completed_procedure(store: InMemoryEventStore) -> None:
    """Append Registered + Started + Completed for a terminal Procedure."""
    from cora.operation.aggregates.procedure import ProcedureCompleted

    await _seed_running_procedure(store)
    completed = ProcedureCompleted(procedure_id=_PROCEDURE_ID, occurred_at=_PRIOR)
    new_event = to_new_event(
        event_type=event_type_name(completed),
        payload=to_payload(completed),
        occurred_at=completed.occurred_at,
        event_id=uuid4(),
        command_name="CompleteProcedure",
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="Procedure",
        stream_id=_PROCEDURE_ID,
        expected_version=2,
        events=[new_event],
    )


def _entry(
    *,
    event_id: UUID | None = None,
    step_kind: str = "setpoint",
    payload: dict[str, object] | None = None,
) -> ProcedureStepInput:
    return ProcedureStepInput(
        event_id=event_id or uuid4(),
        step_kind=step_kind,
        payload=payload or {"channel": "T_oven", "target_value": 423.0},
        sampled_at=_NOW,
    )


# ---------- Happy path: lazy-open + append ----------


@pytest.mark.unit
async def test_handler_lazy_opens_logbook_on_first_append() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_LOGBOOK_ID, _OPEN_EVENT_ID], now=_NOW, event_store=store)
    step_store = InMemoryStepStore()
    handler = append_procedure_step.bind(deps, step_store=step_store)

    count = await handler(
        AppendProcedureSteps(
            procedure_id=_PROCEDURE_ID,
            entries=(_entry(),),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert count == 1
    # Procedure stream gained the lazy-open envelope event.
    events, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 3
    assert events[2].event_type == "ProcedureStepsLogbookOpened"
    # Folded state has the logbook id set.
    state = fold([from_stored(s) for s in events])
    assert state is not None
    assert state.steps_logbook_id == _LOGBOOK_ID
    # Step row landed in the store.
    rows = step_store.all()
    assert len(rows) == 1
    assert rows[0].logbook_id == _LOGBOOK_ID
    assert rows[0].procedure_id == _PROCEDURE_ID
    assert rows[0].step_kind == "setpoint"


@pytest.mark.unit
async def test_handler_skips_open_on_second_append() -> None:
    """First append opens the logbook; second append finds it open and skips."""
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_LOGBOOK_ID, _OPEN_EVENT_ID], now=_NOW, event_store=store)
    step_store = InMemoryStepStore()
    handler = append_procedure_step.bind(deps, step_store=step_store)

    await handler(
        AppendProcedureSteps(procedure_id=_PROCEDURE_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Second handler call: no new ids needed for an open event (we
    # don't open again); we'd only need a fresh deps for the next call.
    deps2 = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler2 = append_procedure_step.bind(deps2, step_store=step_store)
    await handler2(
        AppendProcedureSteps(procedure_id=_PROCEDURE_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Only ONE ProcedureStepsLogbookOpened on the stream.
    events, version = await store.load("Procedure", _PROCEDURE_ID)
    open_count = sum(1 for e in events if e.event_type == "ProcedureStepsLogbookOpened")
    assert open_count == 1
    assert version == 3  # Registered + Started + StepsLogbookOpened
    # Both rows persisted.
    assert len(step_store.all()) == 2


@pytest.mark.unit
async def test_handler_appends_batch_in_one_call() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_LOGBOOK_ID, _OPEN_EVENT_ID], now=_NOW, event_store=store)
    step_store = InMemoryStepStore()
    handler = append_procedure_step.bind(deps, step_store=step_store)

    entries = tuple(_entry(step_kind=k) for k in ("setpoint", "action", "check"))
    count = await handler(
        AppendProcedureSteps(procedure_id=_PROCEDURE_ID, entries=entries),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 3
    rows = step_store.all()
    kinds = {r.step_kind for r in rows}
    assert kinds == {"setpoint", "action", "check"}


@pytest.mark.unit
async def test_handler_dedups_via_event_id() -> None:
    """Producer retries with same event_id: silent dedup at store layer."""
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_LOGBOOK_ID, _OPEN_EVENT_ID], now=_NOW, event_store=store)
    step_store = InMemoryStepStore()
    handler = append_procedure_step.bind(deps, step_store=step_store)

    eid = uuid4()
    await handler(
        AppendProcedureSteps(procedure_id=_PROCEDURE_ID, entries=(_entry(event_id=eid),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    await append_procedure_step.bind(deps2, step_store=step_store)(
        AppendProcedureSteps(
            procedure_id=_PROCEDURE_ID,
            entries=(_entry(event_id=eid, step_kind="action"),),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Only one row; first wins per ON CONFLICT DO NOTHING semantics.
    rows = step_store.all()
    assert len(rows) == 1
    assert rows[0].step_kind == "setpoint"


@pytest.mark.unit
async def test_handler_threads_envelope_correlation_and_actor() -> None:
    """Row's correlation_id + actor_id come from the command envelope."""
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_LOGBOOK_ID, _OPEN_EVENT_ID], now=_NOW, event_store=store)
    step_store = InMemoryStepStore()
    handler = append_procedure_step.bind(deps, step_store=step_store)

    await handler(
        AppendProcedureSteps(procedure_id=_PROCEDURE_ID, entries=(_entry(),)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    row = step_store.all()[0]
    assert row.correlation_id == _CORRELATION_ID
    assert row.actor_id == _PRINCIPAL_ID
    assert row.causation_id is None


# ---------- Error paths ----------


@pytest.mark.unit
async def test_handler_raises_when_procedure_not_found() -> None:
    store = InMemoryEventStore()  # empty
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler = append_procedure_step.bind(deps, step_store=InMemoryStepStore())
    with pytest.raises(ProcedureNotFoundError):
        await handler(
            AppendProcedureSteps(procedure_id=_PROCEDURE_ID, entries=(_entry(),)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_steps_logbook_closed_when_terminal() -> None:
    store = InMemoryEventStore()
    await _seed_completed_procedure(store)
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler = append_procedure_step.bind(deps, step_store=InMemoryStepStore())
    with pytest.raises(ProcedureStepsLogbookClosedError):
        await handler(
            AppendProcedureSteps(procedure_id=_PROCEDURE_ID, entries=(_entry(),)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_steps_logbook_closed_when_defined() -> None:
    """Defined (pre-start) Procedures also reject step appends; only Running accepts."""
    store = InMemoryEventStore()
    # Seed only the Registered event (Defined, not Running).
    registered = ProcedureRegistered(
        procedure_id=_PROCEDURE_ID,
        name="X",
        kind="bakeout",
        target_asset_ids=[],
        parent_run_id=None,
        occurred_at=_PRIOR,
    )
    new_event = to_new_event(
        event_type=event_type_name(registered),
        payload=to_payload(registered),
        occurred_at=registered.occurred_at,
        event_id=uuid4(),
        command_name="RegisterProcedure",
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="Procedure",
        stream_id=_PROCEDURE_ID,
        expected_version=0,
        events=[new_event],
    )

    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler = append_procedure_step.bind(deps, step_store=InMemoryStepStore())
    with pytest.raises(ProcedureStepsLogbookClosedError):
        await handler(
            AppendProcedureSteps(procedure_id=_PROCEDURE_ID, entries=(_entry(),)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_step_kind() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler = append_procedure_step.bind(deps, step_store=InMemoryStepStore())
    with pytest.raises(InvalidStepKindError):
        await handler(
            AppendProcedureSteps(
                procedure_id=_PROCEDURE_ID,
                entries=(_entry(step_kind="not-a-kind"),),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store, deny=True)
    handler = append_procedure_step.bind(deps, step_store=InMemoryStepStore())
    with pytest.raises(UnauthorizedError):
        await handler(
            AppendProcedureSteps(procedure_id=_PROCEDURE_ID, entries=(_entry(),)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store, deny=True)
    step_store = InMemoryStepStore()
    handler = append_procedure_step.bind(deps, step_store=step_store)
    with pytest.raises(UnauthorizedError):
        await handler(
            AppendProcedureSteps(procedure_id=_PROCEDURE_ID, entries=(_entry(),)),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 2  # only the seeded Registered + Started; no open event
    assert step_store.all() == []
