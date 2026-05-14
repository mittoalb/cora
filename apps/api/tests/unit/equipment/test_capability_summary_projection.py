"""Unit tests for CapabilitySummaryProjection.

Pins per-event-type apply() dispatch + idempotency for the 3
subscribed Capability events. Postgres-side behavior is in the
integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.equipment.projections import CapabilitySummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_CAPABILITY_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Capability",
        stream_id=_CAPABILITY_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_projection_metadata() -> None:
    proj = CapabilitySummaryProjection()
    assert proj.name == "proj_equipment_capability_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "CapabilityDefined",
            "CapabilityVersioned",
            "CapabilityDeprecated",
            "CapabilitySettingsSchemaUpdated",
        }
    )


@pytest.mark.unit
async def test_projection_does_not_subscribe_to_asset_events() -> None:
    """Asset events belong in the AssetSummaryProjection (8e-3a)."""
    proj = CapabilitySummaryProjection()
    assert "AssetRegistered" not in proj.subscribed_event_types
    assert "AssetActivated" not in proj.subscribed_event_types


@pytest.mark.unit
async def test_capability_defined_inserts_with_defined_status_and_null_version() -> None:
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CapabilityDefined",
        {
            "capability_id": str(_CAPABILITY_ID),
            "name": "Continuous Rotation Tomography",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_equipment_capability_summary" in sql
    assert "ON CONFLICT (capability_id) DO NOTHING" in sql
    assert "'Defined'" in sql
    assert "NULL" in sql
    assert args.args[1] == _CAPABILITY_ID
    assert args.args[2] == "Continuous Rotation Tomography"
    assert args.args[3] == _NOW


@pytest.mark.unit
async def test_capability_versioned_updates_status_and_version_tag() -> None:
    """CapabilityVersioned writes both status=Versioned AND the new
    version_tag from the payload (the only event that touches the
    version_tag column)."""
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CapabilityVersioned",
        {
            "capability_id": str(_CAPABILITY_ID),
            "version_tag": "v2.1.0",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_capability_summary" in sql
    assert "SET status = 'Versioned'" in sql
    assert "version_tag = $2" in sql
    assert args.args[1] == _CAPABILITY_ID
    assert args.args[2] == "v2.1.0"


@pytest.mark.unit
async def test_capability_deprecated_updates_status_and_preserves_version_tag() -> None:
    """CapabilityDeprecated only touches `status`; `version_tag` is
    intentionally left alone so the audit trail of "what was the
    last revision before deprecation?" stays visible in the
    projection."""
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CapabilityDeprecated",
        {
            "capability_id": str(_CAPABILITY_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_capability_summary" in sql
    assert "SET status = 'Deprecated'" in sql
    assert "version_tag" not in sql
    assert args.args[1] == _CAPABILITY_ID


@pytest.mark.unit
async def test_unknown_event_type_falls_through_match() -> None:
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_asset_registered_is_silently_dropped() -> None:
    """Cross-aggregate-event guard: AssetRegistered isn't in
    subscribed_event_types, but if the SQL filter ever lets one
    through, the bare match drops it without error."""
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored("AssetRegistered", {"asset_id": str(uuid4())})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


# ---- Phase 5g-a: settings_schema_present folding -------------------------


_TEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"energy_kev": {"type": "number"}},
}


@pytest.mark.unit
async def test_capability_settings_schema_updated_with_schema_sets_present_true() -> None:
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CapabilitySettingsSchemaUpdated",
        {
            "capability_id": str(_CAPABILITY_ID),
            "settings_schema": _TEST_SCHEMA,
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_capability_summary" in sql
    assert "settings_schema_present = $2" in sql
    assert args.args[1] == _CAPABILITY_ID
    assert args.args[2] is True


@pytest.mark.unit
async def test_capability_settings_schema_updated_with_none_sets_present_false() -> None:
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CapabilitySettingsSchemaUpdated",
        {
            "capability_id": str(_CAPABILITY_ID),
            "settings_schema": None,
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[2] is False


@pytest.mark.unit
async def test_capability_settings_schema_updated_missing_payload_key_treated_as_none() -> None:
    """Tolerates payloads without the settings_schema key (treats as
    None / FALSE). Matches the from_stored additive-evolution
    stance."""
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CapabilitySettingsSchemaUpdated",
        {
            "capability_id": str(_CAPABILITY_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[2] is False


@pytest.mark.unit
async def test_capability_defined_inserts_with_schema_present_false() -> None:
    """The genesis INSERT must default settings_schema_present to
    FALSE (no schema declared yet); pinned because the column
    default is FALSE in the migration AND the SQL literal is FALSE
    in _INSERT_CAPABILITY_SQL."""
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CapabilityDefined",
        {
            "capability_id": str(_CAPABILITY_ID),
            "name": "Tomography",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "FALSE" in sql  # explicit FALSE in INSERT
