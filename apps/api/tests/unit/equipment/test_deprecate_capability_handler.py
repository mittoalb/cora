"""Unit tests for the `deprecate_capability` application handler.

Mirror of `test_version_capability_handler.py` (single-field
command, no version_tag). Tests cover both source states + the
strict-not-idempotent re-deprecate guard.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.capability import (
    CapabilityCannotDeprecateError,
    CapabilityNotFoundError,
)
from cora.equipment.features import (
    define_capability,
    deprecate_capability,
    version_capability,
)
from cora.equipment.features.define_capability import DefineCapability
from cora.equipment.features.deprecate_capability import DeprecateCapability
from cora.equipment.features.version_capability import VersionCapability
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000000cb01")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000cb02")
_VERSIONED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000cb03")
_DEPRECATED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000cb04")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    return _build_deps_shared(
        ids=[_CAPABILITY_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _define_capability_helper(deps: Kernel) -> UUID:
    return await define_capability.bind(deps)(
        DefineCapability(name="Tomography"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    capability_id = await _define_capability_helper(deps)

    result = await deprecate_capability.bind(deps)(
        DeprecateCapability(capability_id=capability_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_capability_deprecated_event_from_defined() -> None:
    """Direct deprecation (no prior version)."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    capability_id = await _define_capability_helper(deps)

    await deprecate_capability.bind(deps)(
        DeprecateCapability(capability_id=capability_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Capability", capability_id)
    assert version == 2
    assert [e.event_type for e in events] == [
        "CapabilityDefined",
        "CapabilityDeprecated",
    ]
    deprecated = events[1]
    # FixedIdGenerator: defining consumes _CAPABILITY_ID + _DEFINED_EVENT_ID,
    # then deprecate consumes _VERSIONED_EVENT_ID (intended for versioning,
    # but skipped here; the next id from the list).
    assert deprecated.event_id == _VERSIONED_EVENT_ID
    assert deprecated.metadata == {"command": "DeprecateCapability"}


@pytest.mark.unit
async def test_handler_appends_capability_deprecated_event_from_versioned() -> None:
    """Full lifecycle: define → version → deprecate."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    capability_id = await _define_capability_helper(deps)

    await version_capability.bind(deps)(
        VersionCapability(capability_id=capability_id, version_tag="v2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await deprecate_capability.bind(deps)(
        DeprecateCapability(capability_id=capability_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Capability", capability_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "CapabilityDefined",
        "CapabilityVersioned",
        "CapabilityDeprecated",
    ]
    deprecated = events[2]
    assert deprecated.event_id == _DEPRECATED_EVENT_ID


@pytest.mark.unit
async def test_handler_raises_capability_not_found_when_capability_does_not_exist() -> None:
    deps = _build_deps()
    handler = deprecate_capability.bind(deps)

    with pytest.raises(CapabilityNotFoundError):
        await handler(
            DeprecateCapability(capability_id=_CAPABILITY_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_deprecate_when_already_deprecated() -> None:
    """Strict-not-idempotent."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    capability_id = await _define_capability_helper(deps)

    handler = deprecate_capability.bind(deps)
    await handler(
        DeprecateCapability(capability_id=capability_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(CapabilityCannotDeprecateError):
        await handler(
            DeprecateCapability(capability_id=capability_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    capability_id = await _define_capability_helper(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError) as exc_info:
        await deprecate_capability.bind(deny_deps)(
            DeprecateCapability(capability_id=capability_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    capability_id = await _define_capability_helper(deps)

    await deprecate_capability.bind(deps)(
        DeprecateCapability(capability_id=capability_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Capability", capability_id)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_includes_deprecate_capability() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.deprecate_capability)
