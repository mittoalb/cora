"""Unit tests for SupplySummaryProjection.

Pins per-event-type apply() dispatch + idempotency for the 2
subscribed Supply events. Postgres-side behavior is in the
integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import asyncpg
import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.supply.projections import SupplySummaryProjection


def _conn_with_savepoint() -> AsyncMock:
    """AsyncMock conn whose `transaction()` returns an async context manager.

    The projection's `SupplyRegistered` arm wraps its INSERT in
    `async with conn.transaction(): ...` so a UniqueViolation rolls
    back only the inner SAVEPOINT (not the worker's outer batch txn).
    The unit test mock needs to satisfy that protocol shape.
    """
    conn = AsyncMock()
    transaction_cm = AsyncMock()
    transaction_cm.__aenter__.return_value = None
    transaction_cm.__aexit__.return_value = None
    conn.transaction = MagicMock(return_value=transaction_cm)
    return conn


_SUPPLY_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Supply",
        stream_id=_SUPPLY_ID,
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
    proj = SupplySummaryProjection()
    assert proj.name == "proj_supply_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "SupplyRegistered",
            "SupplyMarkedAvailable",
            "SupplyDegraded",
            "SupplyMarkedUnavailable",
            "SupplyMarkedRecovering",
            "SupplyRestored",
            "SupplyDeregistered",
        }
    )


@pytest.mark.unit
def test_projection_does_not_subscribe_to_unrelated_events() -> None:
    """Asset / Family / Run events belong to other projections."""
    proj = SupplySummaryProjection()
    for foreign in (
        "AssetRegistered",
        "FamilyDefined",
        "RunStarted",
        "SubjectMounted",
    ):
        assert foreign not in proj.subscribed_event_types


@pytest.mark.unit
async def test_supply_registered_inserts_with_unknown_status_and_null_audit() -> None:
    proj = SupplySummaryProjection()
    conn = _conn_with_savepoint()
    event = _stored(
        "SupplyRegistered",
        {
            "supply_id": str(_SUPPLY_ID),
            "scope": "Beamline",
            "kind": "LiquidNitrogen",
            "name": "2-BM LN2",
            "facility_code": "cora",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    conn.transaction.assert_called_once()  # SAVEPOINT engaged for the INSERT
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_supply_summary" in sql
    assert "ON CONFLICT (supply_id) DO NOTHING" in sql
    assert "'Unknown'" in sql  # status literal
    # Bound parameters ($1-$7):
    #   supply_id, scope, kind, name, facility_code, containing_asset_id, registered_at
    # containing_asset_id absent from payload -> None (facility-scope semantics).
    assert args.args[1] == _SUPPLY_ID
    assert args.args[2] == "Beamline"
    assert args.args[3] == "LiquidNitrogen"
    assert args.args[4] == "2-BM LN2"
    assert args.args[5] == "cora"
    assert args.args[6] is None
    assert args.args[7] == _NOW


@pytest.mark.unit
async def test_supply_registered_inserts_with_containing_asset_id_when_present() -> None:
    """Slice 7B: when the SupplyRegistered payload carries
    `containing_asset_id`, the projection writer wraps the string-form
    UUID into a typed `UUID` and binds it at position $6."""
    proj = SupplySummaryProjection()
    conn = _conn_with_savepoint()
    containing_asset_id = uuid4()
    event = _stored(
        "SupplyRegistered",
        {
            "supply_id": str(_SUPPLY_ID),
            "scope": "Beamline",
            "kind": "LiquidNitrogen",
            "name": "2-BM LN2",
            "facility_code": "cora",
            "containing_asset_id": str(containing_asset_id),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[6] == containing_asset_id


@pytest.mark.parametrize(
    ("event_type", "expected_status"),
    [
        ("SupplyMarkedAvailable", "Available"),
        ("SupplyDegraded", "Degraded"),
        ("SupplyMarkedUnavailable", "Unavailable"),
        ("SupplyMarkedRecovering", "Recovering"),
        ("SupplyRestored", "Available"),
        ("SupplyDeregistered", "Decommissioned"),
    ],
)
@pytest.mark.unit
async def test_transition_events_share_parameterized_update_with_audit_triple(
    event_type: str, expected_status: str
) -> None:
    """All 6 transition events use the parameterized
    `_UPDATE_STATUS_SQL`; status comes from the per-event-type lookup.
    Pins audit-triple binding (last_status_changed_at = $2,
    last_status_reason = $3, last_trigger = $4, status = $5)."""
    proj = SupplySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        event_type,
        {
            "supply_id": str(_SUPPLY_ID),
            "from_status": "Unknown",
            "reason": "operator gesture",
            "trigger": "Operator",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_supply_summary" in sql
    assert "SET status = $5" in sql  # parameterized, not literal per-status
    assert args.args[1] == _SUPPLY_ID
    assert args.args[2] == _NOW  # last_status_changed_at
    assert args.args[3] == "operator gesture"  # last_status_reason
    assert args.args[4] == "Operator"  # last_trigger
    assert args.args[5] == expected_status  # status (parameterized)


@pytest.mark.unit
async def test_projection_ignores_unsubscribed_event_type() -> None:
    """Foreign event types passed to apply() are no-ops (the worker should never
    deliver them, but defensive guard ensures we don't crash on contamination)."""
    proj = SupplySummaryProjection()
    conn = AsyncMock()
    await proj.apply(_stored("ImaginaryEvent", {}), conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_supply_registered_swallows_unique_violation_and_logs_warn() -> None:
    """Cross-stream duplicate on (scope, kind, name) raises UniqueViolation
    inside the SAVEPOINT; the projection catches it, logs, and returns
    cleanly so the worker's outer batch txn can keep advancing."""
    proj = SupplySummaryProjection()
    conn = _conn_with_savepoint()
    # Make the INSERT raise UniqueViolation
    conn.execute.side_effect = asyncpg.UniqueViolationError("duplicate (scope,kind,name)")
    event = _stored(
        "SupplyRegistered",
        {
            "supply_id": str(_SUPPLY_ID),
            "scope": "Beamline",
            "kind": "LiquidNitrogen",
            "name": "2-BM LN2",
            "facility_code": "cora",
            "occurred_at": _NOW.isoformat(),
        },
    )

    # Must NOT raise — the projection swallows the duplicate.
    await proj.apply(event, conn)

    # SAVEPOINT was engaged + INSERT was attempted
    conn.transaction.assert_called_once()
    conn.execute.assert_awaited_once()
