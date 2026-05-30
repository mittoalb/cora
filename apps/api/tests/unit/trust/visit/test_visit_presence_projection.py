"""Unit tests for `VisitPresenceProjection`.

Pins per-event-type apply() dispatch + idempotency. Postgres-side
behavior is exercised in the integration-tier projection-worker tests.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.trust.projections import VisitPresenceProjection

_VID = UUID("01900000-0000-7000-8000-00000000e001")
_AID = UUID("01900000-0000-7000-8000-00000000e002")
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


@pytest.mark.unit
def test_projection_metadata() -> None:
    proj = VisitPresenceProjection()
    assert proj.name == "proj_trust_visit_presence"
    assert proj.subscribed_event_types == frozenset({"VisitCheckedIn", "VisitCheckedOut"})


@pytest.mark.unit
async def test_apply_skips_unsubscribed_event_type() -> None:
    proj = VisitPresenceProjection()
    conn = AsyncMock()
    event = _stored("VisitArrived", {"visit_id": str(_VID), "occurred_at": _NOW.isoformat()})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_visit_checked_in_inserts_open_presence_row() -> None:
    proj = VisitPresenceProjection()
    conn = AsyncMock()
    event = _stored(
        "VisitCheckedIn",
        {
            "visit_id": str(_VID),
            "actor_id": str(_AID),
            "mode": "physical",
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql: str = args.args[0]
    assert "INSERT INTO proj_trust_visit_presence" in sql
    assert "ON CONFLICT (visit_id, actor_id, check_in_at) DO NOTHING" in sql
    assert args.args[1] == _VID
    assert args.args[2] == _AID
    assert args.args[3] == "physical"


@pytest.mark.unit
async def test_visit_checked_in_carries_remote_mode_through_to_insert() -> None:
    proj = VisitPresenceProjection()
    conn = AsyncMock()
    event = _stored(
        "VisitCheckedIn",
        {
            "visit_id": str(_VID),
            "actor_id": str(_AID),
            "mode": "remote",
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert args.args[3] == "remote"


@pytest.mark.unit
async def test_visit_checked_out_updates_open_entry_only() -> None:
    proj = VisitPresenceProjection()
    conn = AsyncMock()
    event = _stored(
        "VisitCheckedOut",
        {
            "visit_id": str(_VID),
            "actor_id": str(_AID),
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    sql: str = args.args[0]
    assert "UPDATE proj_trust_visit_presence" in sql
    assert "check_out_at = $3" in sql
    assert "check_out_at IS NULL" in sql
    assert args.args[1] == _VID
    assert args.args[2] == _AID
    assert args.args[3] == _NOW
