"""Unit tests for the `define_capability` application handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.capability import InvalidCapabilityNameError
from cora.equipment.features import define_capability
from cora.equipment.features.define_capability import DefineCapability
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000006ab1")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000006be1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    return _build_deps_shared(
        ids=[_NEW_ID, _EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


@pytest.mark.unit
async def test_handler_returns_generated_capability_id() -> None:
    deps = _build_deps()
    handler = define_capability.bind(deps)

    result = await handler(
        DefineCapability(name="Tomography"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_capability_defined_event_to_store() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_capability.bind(deps)

    await handler(
        DefineCapability(name="Tomography"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Capability", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "CapabilityDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "capability_id": str(_NEW_ID),
        "name": "Tomography",
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefineCapability"}
    assert stored.occurred_at == _NOW


@pytest.mark.unit
async def test_handler_trims_capability_name_via_value_object() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_capability.bind(deps)

    await handler(
        DefineCapability(name="  Tomography  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Capability", _NEW_ID)
    assert events[0].payload["name"] == "Tomography"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)
    handler = define_capability.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            DefineCapability(name="Tomography"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = define_capability.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            DefineCapability(name="Tomography"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Capability", _NEW_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_propagates_invalid_capability_name_error() -> None:
    deps = _build_deps()
    handler = define_capability.bind(deps)

    with pytest.raises(InvalidCapabilityNameError):
        await handler(
            DefineCapability(name="   "),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_capability.bind(deps)

    await handler(
        DefineCapability(name="Tomography"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Capability", _NEW_ID)
    assert events[0].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_returns_handlers_bundle() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.define_capability)
    assert callable(handlers.get_capability)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end check that causation_id survives the
    `with_tracing(with_idempotency(bare))` chain in wire.py."""
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handlers = wire_equipment(deps)

    await handlers.define_capability(
        DefineCapability(name="Tomography"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Capability", _NEW_ID)
    assert events[0].causation_id == causation
