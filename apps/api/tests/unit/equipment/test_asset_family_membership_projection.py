"""Unit tests for AssetFamilyMembershipProjection.

Pins per-event-type apply() dispatch + idempotency for the 2
subscribed Asset<->Family membership events. Postgres-side behavior
(actual INSERT/DELETE round-trips, index visibility) is in the
integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.equipment.projections.asset_family_membership import AssetFamilyMembershipProjection
from cora.infrastructure.ports.event_store import StoredEvent

_ASSET_ID = uuid4()
_FAMILY_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 27, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Asset",
        stream_id=_ASSET_ID,
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
    proj = AssetFamilyMembershipProjection()
    assert proj.name == "proj_equipment_asset_family_membership"
    assert proj.subscribed_event_types == frozenset({"AssetFamilyAdded", "AssetFamilyRemoved"})


@pytest.mark.unit
async def test_asset_family_added_inserts_join_row() -> None:
    proj = AssetFamilyMembershipProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetFamilyAdded",
        {
            "asset_id": str(_ASSET_ID),
            "family_id": str(_FAMILY_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_equipment_asset_family_membership" in sql
    assert "ON CONFLICT (asset_id, family_id) DO NOTHING" in sql
    assert args.args[1] == _ASSET_ID
    assert args.args[2] == _FAMILY_ID
    assert args.args[3] == _NOW


@pytest.mark.unit
async def test_asset_family_removed_deletes_join_row() -> None:
    proj = AssetFamilyMembershipProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetFamilyRemoved",
        {
            "asset_id": str(_ASSET_ID),
            "family_id": str(_FAMILY_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "DELETE FROM proj_equipment_asset_family_membership" in sql
    assert args.args[1] == _ASSET_ID
    assert args.args[2] == _FAMILY_ID
