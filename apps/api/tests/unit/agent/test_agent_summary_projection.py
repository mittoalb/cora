"""Unit tests for AgentSummaryProjection.

Pins per-event-type apply() dispatch + idempotency for the 3
subscribed Agent lifecycle events. Postgres-side behavior is in the
integration suite. Mirrors test_method/plan/practice/family/recipe_capability_summary_projection.py.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.agent.projections import AgentSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_AGENT_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 19, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Agent",
        stream_id=_AGENT_ID,
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
    proj = AgentSummaryProjection()
    assert proj.name == "proj_agent_summary"
    assert proj.subscribed_event_types == frozenset(
        {"AgentDefined", "AgentVersioned", "AgentDeprecated"}
    )


@pytest.mark.unit
async def test_projection_does_not_subscribe_to_suspend_resume_events() -> None:
    """Suspended/Resumed events (8f-c iter 2) stay on aggregate state
    because `suspension_reason` is invariant-bearing — only derivable
    lifecycle timestamps move to projection."""
    proj = AgentSummaryProjection()
    assert "AgentSuspended" not in proj.subscribed_event_types
    assert "AgentResumed" not in proj.subscribed_event_types


@pytest.mark.unit
async def test_agent_defined_inserts_with_defined_status() -> None:
    proj = AgentSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AgentDefined",
        {
            "agent_id": str(_AGENT_ID),
            "kind": "RunDebrief",
            "name": "RunDebriefAgent",
            "version": "v1",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_agent_summary" in sql
    assert "ON CONFLICT (agent_id) DO NOTHING" in sql
    assert "'Defined'" in sql
    assert args.args[1] == _AGENT_ID
    assert args.args[2] == "RunDebrief"
    assert args.args[3] == "RunDebriefAgent"
    assert args.args[4] == "v1"
    assert args.args[5] == _NOW


@pytest.mark.unit
async def test_agent_versioned_updates_status_version_and_versioned_at() -> None:
    proj = AgentSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AgentVersioned",
        {
            "agent_id": str(_AGENT_ID),
            "version": "v2",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_agent_summary" in sql
    assert "SET status = 'Versioned'" in sql
    assert "version = $2" in sql
    assert "versioned_at = $3" in sql
    assert args.args[1] == _AGENT_ID
    assert args.args[2] == "v2"
    assert args.args[3] == _NOW


@pytest.mark.unit
async def test_agent_versioned_replayed_overwrites_versioned_at() -> None:
    """Path C: re-version replaces versioned_at wholesale (state-always-
    holds-latest convention mirrored in projection)."""
    proj = AgentSummaryProjection()
    conn = AsyncMock()
    later = datetime(2026, 6, 1, 9, 30, 0, tzinfo=UTC)

    first = _stored(
        "AgentVersioned",
        {"agent_id": str(_AGENT_ID), "version": "v2", "occurred_at": _NOW.isoformat()},
    )
    second = _stored(
        "AgentVersioned",
        {"agent_id": str(_AGENT_ID), "version": "v3", "occurred_at": later.isoformat()},
    )

    await proj.apply(first, conn)
    await proj.apply(second, conn)

    assert conn.execute.await_count == 2
    second_args = conn.execute.await_args_list[1].args
    assert second_args[2] == "v3"
    assert second_args[3] == later


@pytest.mark.unit
async def test_agent_deprecated_updates_status_and_deprecated_at() -> None:
    proj = AgentSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AgentDeprecated",
        {"agent_id": str(_AGENT_ID), "occurred_at": _NOW.isoformat()},
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_agent_summary" in sql
    assert "SET status = 'Deprecated'" in sql
    assert "deprecated_at = $2" in sql
    assert "version" not in sql  # version is preserved on deprecation
    assert args.args[1] == _AGENT_ID
    assert args.args[2] == _NOW


@pytest.mark.unit
async def test_unknown_event_type_falls_through_match() -> None:
    proj = AgentSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_agent_suspended_silently_dropped() -> None:
    """Iter C-1 scope: Suspended/Resumed events stay on aggregate state
    (decider-relevant via suspension_reason). The projection's
    subscribed_event_types intentionally excludes them; the bare match
    arm drops them without writing the read model."""
    proj = AgentSummaryProjection()
    conn = AsyncMock()
    event = _stored("AgentSuspended", {"agent_id": str(_AGENT_ID)})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()
