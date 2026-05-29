"""Unit tests for `SurfaceActiveVisitProjection`.

Pins per-event-type apply() dispatch + the 2-statement transactional
shape for VisitTookControlOfSurface. Postgres-side behavior is
exercised in the integration-tier projection-worker tests.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.trust.projections import SurfaceActiveVisitProjection

_VID = UUID("01900000-0000-7000-8000-00000000d001")
_SID = UUID("01900000-0000-7000-8000-00000000d002")
_NOW = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Visit",
        stream_id=_VID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


def _conn_with_transaction() -> AsyncMock:
    """Build a mock connection whose `transaction()` returns an async context manager."""
    conn = AsyncMock()
    tx_cm = MagicMock()
    tx_cm.__aenter__ = AsyncMock(return_value=tx_cm)
    tx_cm.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=tx_cm)
    return conn


@pytest.mark.unit
def test_projection_metadata() -> None:
    proj = SurfaceActiveVisitProjection()
    assert proj.name == "proj_trust_surface_active_visit"
    assert proj.subscribed_event_types == frozenset(
        {"VisitTookControlOfSurface", "VisitReleasedControlOfSurface"}
    )


@pytest.mark.unit
async def test_apply_skips_unsubscribed_event_type() -> None:
    proj = SurfaceActiveVisitProjection()
    conn = AsyncMock()
    event = _stored("VisitArrived", {"visit_id": str(_VID), "occurred_at": _NOW.isoformat()})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()
    conn.transaction.assert_not_called()


@pytest.mark.unit
async def test_took_control_runs_two_statement_transaction() -> None:
    proj = SurfaceActiveVisitProjection()
    conn = _conn_with_transaction()
    event = _stored(
        "VisitTookControlOfSurface",
        {
            "visit_id": str(_VID),
            "surface_id": str(_SID),
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    conn.transaction.assert_called_once()
    assert conn.execute.await_count == 2
    first_call_sql: str = conn.execute.await_args_list[0].args[0]
    second_call_sql: str = conn.execute.await_args_list[1].args[0]
    assert "UPDATE proj_trust_surface_active_visit" in first_call_sql
    assert "released_at IS NULL" in first_call_sql
    assert "INSERT INTO proj_trust_surface_active_visit" in second_call_sql
    assert "ON CONFLICT (surface_id, visit_id, since_at) DO NOTHING" in second_call_sql


@pytest.mark.unit
async def test_released_control_updates_open_row_only() -> None:
    proj = SurfaceActiveVisitProjection()
    conn = AsyncMock()
    event = _stored(
        "VisitReleasedControlOfSurface",
        {
            "visit_id": str(_VID),
            "surface_id": str(_SID),
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql: str = args.args[0]
    assert "UPDATE proj_trust_surface_active_visit" in sql
    assert "released_at IS NULL" in sql
    assert args.args[1] == _SID
    assert args.args[2] == _VID
    assert args.args[3] == _NOW
