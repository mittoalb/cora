"""Application-handler tests for `truncate_procedure` slice (10c-c iter 1).

Update-style handler via `make_procedure_update_handler` (factory
hoisted at rule-of-three when this slice landed). The reason +
interrupted_at fields are captured on the emitted event payload but
intentionally NOT logged at the handler boundary.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.operation.aggregates.procedure import (
    InvalidProcedureInterruptedAtError,
    InvalidProcedureTruncateReasonError,
    ProcedureCannotTruncateError,
    ProcedureNotFoundError,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features import truncate_procedure
from cora.operation.features.truncate_procedure import TruncateProcedure
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.operation._helpers import seed_running_procedure

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 5, 15, 11, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000010c0e01")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000010c0e02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_running_procedure(store: InMemoryEventStore) -> None:
    await seed_running_procedure(
        store,
        procedure_id=_PROCEDURE_ID,
        when=_PRIOR,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )


@pytest.mark.unit
async def test_handler_appends_procedure_truncated_event_with_reason() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = truncate_procedure.bind(deps)

    interrupted_at = _NOW - timedelta(hours=2)
    await handler(
        TruncateProcedure(
            procedure_id=_PROCEDURE_ID,
            reason="  weekend power loss  ",
            interrupted_at=interrupted_at,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 3
    assert events[2].event_type == "ProcedureTruncated"
    assert events[2].payload == {
        "procedure_id": str(_PROCEDURE_ID),
        "reason": "weekend power loss",
        "interrupted_at": interrupted_at.isoformat(),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
async def test_handler_appends_with_null_interrupted_at_when_unknown() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = truncate_procedure.bind(deps)

    await handler(
        TruncateProcedure(procedure_id=_PROCEDURE_ID, reason="unknown when crashed"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Procedure", _PROCEDURE_ID)
    assert events[2].payload["interrupted_at"] is None


@pytest.mark.unit
async def test_handler_raises_when_procedure_not_found() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = truncate_procedure.bind(deps)
    with pytest.raises(ProcedureNotFoundError):
        await handler(
            TruncateProcedure(procedure_id=_PROCEDURE_ID, reason="x"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_truncate_when_re_truncating() -> None:
    """Strict-not-idempotent: re-truncating a Truncated procedure raises."""
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps1 = _build_deps_shared(ids=[uuid4()], now=_NOW, event_store=store)
    await truncate_procedure.bind(deps1)(
        TruncateProcedure(procedure_id=_PROCEDURE_ID, reason="first"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = _build_deps_shared(ids=[uuid4()], now=_NOW, event_store=store)
    with pytest.raises(ProcedureCannotTruncateError):
        await truncate_procedure.bind(deps2)(
            TruncateProcedure(procedure_id=_PROCEDURE_ID, reason="second"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_reason_for_whitespace_only() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = truncate_procedure.bind(deps)
    with pytest.raises(InvalidProcedureTruncateReasonError):
        await handler(
            TruncateProcedure(procedure_id=_PROCEDURE_ID, reason="   "),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_future_interrupted_at() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = truncate_procedure.bind(deps)
    with pytest.raises(InvalidProcedureInterruptedAtError):
        await handler(
            TruncateProcedure(
                procedure_id=_PROCEDURE_ID,
                reason="r",
                interrupted_at=_NOW + timedelta(hours=1),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = truncate_procedure.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            TruncateProcedure(procedure_id=_PROCEDURE_ID, reason="r"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    await _seed_running_procedure(store)
    deps = _build_deps_shared(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = truncate_procedure.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            TruncateProcedure(procedure_id=_PROCEDURE_ID, reason="r"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Procedure", _PROCEDURE_ID)
    assert version == 2  # only Registered + Started; no truncate appended
