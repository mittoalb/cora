"""Unit tests for the `update_capability_settings_schema` application handler.

Phase 5g-a. Mirrors `test_update_method_parameters_schema_handler.py`
shape. Update-style: load + fold + decide + append; no-op on
structurally equal schema; clears to None.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.capability import (
    CapabilityNotFoundError,
    InvalidCapabilitySettingsSchemaError,
)
from cora.equipment.features import define_capability, update_capability_settings_schema
from cora.equipment.features.define_capability import DefineCapability
from cora.equipment.features.update_capability_settings_schema import (
    UpdateCapabilitySettingsSchema,
)
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000000c551")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000c552")
_SCHEMA_EVENT_ID = UUID("01900000-0000-7000-8000-00000000c553")
_SCHEMA_EVENT_ID_2 = UUID("01900000-0000-7000-8000-00000000c554")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _valid_schema(min_val: int = 5) -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "minimum": min_val,
                "unit": {"system": "udunits", "code": "keV"},
            }
        },
    }


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    return _build_deps_shared(
        ids=[_CAPABILITY_ID, _DEFINED_EVENT_ID, _SCHEMA_EVENT_ID, _SCHEMA_EVENT_ID_2],
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

    result = await update_capability_settings_schema.bind(deps)(
        UpdateCapabilitySettingsSchema(
            capability_id=capability_id, settings_schema=_valid_schema()
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_capability_settings_schema_updated_event() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    capability_id = await _define_capability_helper(deps)
    schema = _valid_schema()

    await update_capability_settings_schema.bind(deps)(
        UpdateCapabilitySettingsSchema(capability_id=capability_id, settings_schema=schema),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Capability", capability_id)
    assert version == 2
    assert [e.event_type for e in events] == [
        "CapabilityDefined",
        "CapabilitySettingsSchemaUpdated",
    ]
    schema_event = events[1]
    assert schema_event.event_id == _SCHEMA_EVENT_ID
    assert schema_event.metadata == {"command": "UpdateCapabilitySettingsSchema"}
    assert schema_event.payload["settings_schema"] == schema


@pytest.mark.unit
async def test_handler_no_op_on_unchanged_schema_does_not_append() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    capability_id = await _define_capability_helper(deps)
    handler = update_capability_settings_schema.bind(deps)
    schema = _valid_schema()

    await handler(
        UpdateCapabilitySettingsSchema(capability_id=capability_id, settings_schema=schema),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await handler(
        UpdateCapabilitySettingsSchema(capability_id=capability_id, settings_schema=schema),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Capability", capability_id)
    assert version == 2  # define + 1 schema-update; second call no-op
    assert [e.event_type for e in events] == [
        "CapabilityDefined",
        "CapabilitySettingsSchemaUpdated",
    ]


@pytest.mark.unit
async def test_handler_supports_setting_then_clearing_schema() -> None:
    """Set, then clear: two events emitted; final state has settings_schema=None."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    capability_id = await _define_capability_helper(deps)
    handler = update_capability_settings_schema.bind(deps)

    await handler(
        UpdateCapabilitySettingsSchema(
            capability_id=capability_id, settings_schema=_valid_schema()
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await handler(
        UpdateCapabilitySettingsSchema(capability_id=capability_id, settings_schema=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Capability", capability_id)
    assert version == 3
    assert events[1].payload["settings_schema"] == _valid_schema()
    assert events[2].payload["settings_schema"] is None


@pytest.mark.unit
async def test_handler_raises_capability_not_found_when_capability_does_not_exist() -> None:
    deps = _build_deps()
    handler = update_capability_settings_schema.bind(deps)

    with pytest.raises(CapabilityNotFoundError):
        await handler(
            UpdateCapabilitySettingsSchema(
                capability_id=_CAPABILITY_ID, settings_schema=_valid_schema()
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_schema_for_missing_dollar_schema() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    capability_id = await _define_capability_helper(deps)

    with pytest.raises(InvalidCapabilitySettingsSchemaError):
        await update_capability_settings_schema.bind(deps)(
            UpdateCapabilitySettingsSchema(
                capability_id=capability_id,
                settings_schema={"type": "object"},  # no $schema
            ),
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
        await update_capability_settings_schema.bind(deny_deps)(
            UpdateCapabilitySettingsSchema(
                capability_id=capability_id, settings_schema=_valid_schema()
            ),
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

    await update_capability_settings_schema.bind(deps)(
        UpdateCapabilitySettingsSchema(
            capability_id=capability_id, settings_schema=_valid_schema()
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Capability", capability_id)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_includes_update_capability_settings_schema() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.update_capability_settings_schema)
