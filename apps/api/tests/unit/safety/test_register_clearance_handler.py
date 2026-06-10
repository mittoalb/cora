"""Application-handler tests for `register_clearance` slice."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.safety.aggregates.clearance import (
    RunBinding,
    SubjectBinding,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.errors import UnauthorizedError
from cora.safety.features import register_clearance
from cora.safety.features.register_clearance import RegisterClearance
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000011011")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000011012")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_FACILITY_CODE = "cora"
_TEMPLATE_CODE = "ESAF"
_TEMPLATE_ID: ClearanceTemplateId = ClearanceTemplateId(
    clearance_template_stream_id(_FACILITY_CODE, _TEMPLATE_CODE)
)


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    deps = _build_deps_shared(
        ids=[_NEW_ID, _EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )
    # Seed the in-memory ClearanceTemplateLookup with an Active "ESAF"
    # template in the "cora" facility so the handler's cross-aggregate
    # template lookup resolves before the decider runs.
    deps.clearance_template_lookup.register(  # type: ignore[attr-defined]
        template_id=_TEMPLATE_ID,
        facility_code=_FACILITY_CODE,
        code=_TEMPLATE_CODE,
        status="Active",
        version=1,
    )
    return deps


@pytest.mark.unit
async def test_handler_returns_generated_clearance_id() -> None:
    deps = _build_deps()
    handler = register_clearance.bind(deps)
    result = await handler(
        RegisterClearance(
            template_id=_TEMPLATE_ID,
            facility_code=_FACILITY_CODE,
            title="Pilot ESAF",
            bindings=frozenset({RunBinding(run_id=UUID(int=42))}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_clearance_registered_event() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_clearance.bind(deps)
    rid = UUID(int=42)
    await handler(
        RegisterClearance(
            template_id=_TEMPLATE_ID,
            facility_code=_FACILITY_CODE,
            title="Pilot ESAF",
            bindings=frozenset({RunBinding(run_id=rid)}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Clearance", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "ClearanceRegistered"
    assert stored.payload["clearance_id"] == str(_NEW_ID)
    assert stored.payload["template_id"] == str(_TEMPLATE_ID)
    assert stored.payload["template_code"] == _TEMPLATE_CODE
    assert stored.payload["title"] == "Pilot ESAF"
    assert stored.payload["bindings"] == [{"kind": "Run", "id": str(rid)}]
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "RegisterClearance"}


@pytest.mark.unit
async def test_handler_serializes_multi_binding_set() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_clearance.bind(deps)
    sid, rid = UUID(int=1), UUID(int=2)
    await handler(
        RegisterClearance(
            template_id=_TEMPLATE_ID,
            facility_code=_FACILITY_CODE,
            title="Multi-bind",
            bindings=frozenset({SubjectBinding(subject_id=sid), RunBinding(run_id=rid)}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Clearance", _NEW_ID)
    binding_kinds = {b["kind"] for b in events[0].payload["bindings"]}
    assert binding_kinds == {"Subject", "Run"}


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)
    handler = register_clearance.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            RegisterClearance(
                template_id=_TEMPLATE_ID,
                facility_code=_FACILITY_CODE,
                title="t",
                bindings=frozenset({RunBinding(run_id=UUID(int=1))}),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = register_clearance.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            RegisterClearance(
                template_id=_TEMPLATE_ID,
                facility_code=_FACILITY_CODE,
                title="t",
                bindings=frozenset({RunBinding(run_id=UUID(int=1))}),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Clearance", _NEW_ID)
    assert version == 0
    assert events == []


@pytest.mark.unit
async def test_handler_records_causation_id_when_provided() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_clearance.bind(deps)
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    await handler(
        RegisterClearance(
            template_id=_TEMPLATE_ID,
            facility_code=_FACILITY_CODE,
            title="t",
            bindings=frozenset({RunBinding(run_id=UUID(int=1))}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Clearance", _NEW_ID)
    assert events[0].causation_id == causation
