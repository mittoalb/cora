"""Application-handler tests for `register_procedure` slice.

In-memory event store + AllowAllAuthorize (or DenyAllAuthorize). The
idempotency-wrap is applied at wire.py and is not exercised here;
we test the bare handler returned by `register_procedure.bind(deps)`.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.operation.errors import UnauthorizedError
from cora.operation.features import register_procedure
from cora.operation.features.register_procedure import RegisterProcedure
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-0000000c0a01")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c0a02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_ASSET_ID = UUID("01900000-0000-7000-8000-0000000c0a11")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEW_ID, _EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


@pytest.mark.unit
async def test_handler_returns_generated_procedure_id() -> None:
    deps = _build_deps()
    handler = register_procedure.bind(deps)
    result = await handler(
        RegisterProcedure(name="Vessel-A bakeout", kind="bakeout"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_procedure_registered_event_to_store() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_procedure.bind(deps)
    await handler(
        RegisterProcedure(
            name="35-BM rotation-axis alignment",
            kind="alignment",
            target_asset_ids=frozenset({_ASSET_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Procedure", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "ProcedureRegistered"
    assert stored.payload == {
        "procedure_id": str(_NEW_ID),
        "name": "35-BM rotation-axis alignment",
        "kind": "alignment",
        "target_asset_ids": [str(_ASSET_ID)],
        "parent_run_id": None,
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "RegisterProcedure"}


@pytest.mark.unit
async def test_handler_appends_phase_of_run_with_parent_run_id() -> None:
    parent_run = UUID("01900000-0000-7000-8000-0000000c0a99")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_procedure.bind(deps)
    await handler(
        RegisterProcedure(
            name="Mid-run calibration sweep",
            kind="calibration",
            parent_run_id=parent_run,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Procedure", _NEW_ID)
    assert events[0].payload["parent_run_id"] == str(parent_run)


@pytest.mark.unit
async def test_handler_trims_kind_and_name() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_procedure.bind(deps)
    await handler(
        RegisterProcedure(name="  Vessel-A bakeout  ", kind="  bakeout  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Procedure", _NEW_ID)
    assert events[0].payload["name"] == "Vessel-A bakeout"
    assert events[0].payload["kind"] == "bakeout"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)
    handler = register_procedure.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            RegisterProcedure(name="X", kind="bakeout"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = register_procedure.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            RegisterProcedure(name="X", kind="bakeout"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Procedure", _NEW_ID)
    assert version == 0
    assert events == []


@pytest.mark.unit
async def test_handler_propagates_causation_id() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_procedure.bind(deps)
    await handler(
        RegisterProcedure(name="X", kind="bakeout"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Procedure", _NEW_ID)
    assert events[0].causation_id == causation


@pytest.mark.unit
def test_wire_operation_includes_register_procedure() -> None:
    from cora.operation import OperationHandlers, wire_operation

    deps = _build_deps()
    handlers = wire_operation(deps)
    assert isinstance(handlers, OperationHandlers)
    assert callable(handlers.register_procedure)
    assert callable(handlers.get_procedure)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end: causation_id survives `with_tracing(with_idempotency(bare))`."""
    from cora.operation import wire_operation

    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handlers = wire_operation(deps)

    await handlers.register_procedure(
        RegisterProcedure(name="Vessel-A bakeout", kind="bakeout"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Procedure", _NEW_ID)
    assert events[0].causation_id == causation
