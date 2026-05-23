"""Application-handler tests for `get_procedure` query slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.operation.aggregates.procedure import (
    ProcedureRegistered,
    ProcedureStatus,
    event_type_name,
    to_payload,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features import get_procedure
from cora.operation.features.get_procedure import GetProcedure
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000000c0a51")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_procedure_registered(
    store: InMemoryEventStore,
    procedure_id: UUID = _PROCEDURE_ID,
) -> None:
    event = ProcedureRegistered(
        procedure_id=procedure_id,
        name="Vessel-A bakeout",
        kind="bakeout",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RegisterProcedure",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=0,
        events=[new_event],
    )


@pytest.mark.unit
async def test_handler_returns_procedure_when_found() -> None:
    store = InMemoryEventStore()
    await _seed_procedure_registered(store)
    deps = build_deps(ids=[uuid4()], now=_NOW, event_store=store)
    handler = get_procedure.bind(deps)
    result = await handler(
        GetProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is not None
    assert result.id == _PROCEDURE_ID
    assert result.name.value == "Vessel-A bakeout"
    assert result.kind == "bakeout"
    assert result.status is ProcedureStatus.DEFINED


@pytest.mark.unit
async def test_handler_returns_none_when_not_found() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4()], now=_NOW, event_store=store)
    handler = get_procedure.bind(deps)
    result = await handler(
        GetProcedure(procedure_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_procedure_registered(store)
    deps = build_deps(ids=[uuid4()], now=_NOW, event_store=store, deny=True)
    handler = get_procedure.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            GetProcedure(procedure_id=_PROCEDURE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
