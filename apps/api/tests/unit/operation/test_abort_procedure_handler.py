"""Application-handler tests for `abort_procedure` slice.

Update-style handler via `make_update_handler`. The reason field is
captured on the emitted event payload but intentionally NOT logged at
the handler boundary (mirrors abort_run precedent).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.operation.aggregates.procedure import (
    InvalidProcedureAbortReasonError,
    ProcedureCannotAbortError,
    ProcedureNotFoundError,
    ProcedureRegistered,
    ProcedureStarted,
    event_type_name,
    to_payload,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features import abort_procedure
from cora.operation.features.abort_procedure import AbortProcedure
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 5, 15, 11, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000c0d01")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c0d02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_running_procedure(store: InMemoryEventStore) -> None:
    """Append Registered + Started events for a Running Procedure."""
    registered = ProcedureRegistered(
        procedure_id=_PROCEDURE_ID,
        name="X",
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


@pytest.mark.unit
async def test_handler_appends_procedure_aborted_event_with_trimmed_reason() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = abort_procedure.bind(deps)

    await handler(
        AbortProcedure(procedure_id=_PROCEDURE_ID, reason="  vacuum loss  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 3
    assert events[2].event_type == "ProcedureAborted"
    assert events[2].payload == {
        "procedure_id": str(_PROCEDURE_ID),
        "reason": "vacuum loss",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
async def test_handler_raises_when_procedure_not_found() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = abort_procedure.bind(deps)
    with pytest.raises(ProcedureNotFoundError):
        await handler(
            AbortProcedure(procedure_id=_PROCEDURE_ID, reason="x"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_abort_when_re_aborting() -> None:
    """Strict-not-idempotent: re-aborting an Aborted procedure raises."""
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps1 = _build_deps_shared(ids=[uuid4()], now=_NOW, event_store=store)
    await abort_procedure.bind(deps1)(
        AbortProcedure(procedure_id=_PROCEDURE_ID, reason="first"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = _build_deps_shared(ids=[uuid4()], now=_NOW, event_store=store)
    with pytest.raises(ProcedureCannotAbortError):
        await abort_procedure.bind(deps2)(
            AbortProcedure(procedure_id=_PROCEDURE_ID, reason="second"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_reason_for_whitespace_only() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = abort_procedure.bind(deps)
    with pytest.raises(InvalidProcedureAbortReasonError):
        await handler(
            AbortProcedure(procedure_id=_PROCEDURE_ID, reason="   "),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = abort_procedure.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            AbortProcedure(procedure_id=_PROCEDURE_ID, reason="r"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = abort_procedure.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            AbortProcedure(procedure_id=_PROCEDURE_ID, reason="r"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 2
