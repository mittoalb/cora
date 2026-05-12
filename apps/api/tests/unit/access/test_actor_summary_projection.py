"""Unit tests for ActorSummaryProjection.

Pins per-event-type apply() dispatch + idempotency. Postgres-side
behavior is exercised in `tests/integration/test_projection_worker_postgres.py`.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.access.projections import ActorSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_ACTOR_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Actor",
        stream_id=_ACTOR_ID,
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
    proj = ActorSummaryProjection()
    assert proj.name == "proj_access_actor_summary"
    assert proj.subscribed_event_types == frozenset({"ActorRegistered", "ActorDeactivated"})


@pytest.mark.unit
async def test_actor_registered_inserts_with_active_status() -> None:
    proj = ActorSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ActorRegistered",
        {
            "actor_id": str(_ACTOR_ID),
            "name": "Doga",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_access_actor_summary" in sql
    assert "ON CONFLICT (actor_id) DO NOTHING" in sql
    assert args.args[1] == _ACTOR_ID
    assert args.args[2] == "Doga"
    assert args.args[3] == _NOW


@pytest.mark.unit
async def test_actor_deactivated_updates_status() -> None:
    proj = ActorSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ActorDeactivated",
        {"actor_id": str(_ACTOR_ID), "occurred_at": _NOW.isoformat()},
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_access_actor_summary" in sql
    assert "status = 'deactivated'" in sql
    assert args.args[1] == _ACTOR_ID


@pytest.mark.unit
async def test_unknown_event_type_silently_dropped() -> None:
    """SQL-side filter should never deliver unsubscribed events; the
    defensive fall-through is a belt-and-suspenders no-op."""
    proj = ActorSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})

    await proj.apply(event, conn)

    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_apply_is_idempotent_for_actor_registered() -> None:
    """ON CONFLICT DO NOTHING means re-applying the same
    ActorRegistered event a second time runs the same SQL again,
    which Postgres handles as a no-op. The projection author doesn't
    need to track which events have been seen."""
    proj = ActorSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ActorRegistered",
        {
            "actor_id": str(_ACTOR_ID),
            "name": "Doga",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)
    await proj.apply(event, conn)

    assert conn.execute.await_count == 2
    # Both calls have identical args; Postgres ON CONFLICT semantics
    # make the net effect equivalent to one call.
    first_args = conn.execute.await_args_list[0].args
    second_args = conn.execute.await_args_list[1].args
    assert first_args == second_args
