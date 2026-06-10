"""Unit tests for `ClearanceTemplateSummaryProjection`.

Covers:
  - subscribed_event_types pinned to the 5 currently-shipped events
    (drift-catcher: adding a new event type without widening this set
    leaves the projection silently skipping it)
  - apply() is a no-op for unsubscribed event types (defensive)
  - ClearanceTemplateActivated emits UPDATE status='Active'
  - ClearanceTemplateVersioned emits UPDATE with new_version + supersedes
  - ClearanceTemplateDeprecated emits UPDATE status='Deprecated'
  - ClearanceTemplateWithdrawn emits UPDATE status='Withdrawn'
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.safety.projections import ClearanceTemplateSummaryProjection

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


# ---------- subscribed_event_types lock ----------


@pytest.mark.unit
def test_subscribed_event_types_covers_all_five_clearance_template_events() -> None:
    """Drift-catcher: widening the projection to new events MUST update this set.

    Adding a new event-type without re-pinning this assertion leaves the
    projection silently skipping the event because the worker dispatches
    on subscribed_event_types.
    """
    proj = ClearanceTemplateSummaryProjection()
    assert proj.subscribed_event_types == frozenset(
        {
            "ClearanceTemplateDefined",
            "ClearanceTemplateActivated",
            "ClearanceTemplateVersioned",
            "ClearanceTemplateDeprecated",
            "ClearanceTemplateWithdrawn",
        }
    )


# ---------- apply() dispatch via recording fake connection ----------


class _RecordingConn:
    """Captures (sql, args) tuples for each execute call. No-op driver."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, sql: str, *args: object) -> None:
        self.calls.append((sql, args))


def _stored(
    event_type: str,
    payload: dict[str, Any],
    *,
    principal_id: UUID | None = None,
) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="ClearanceTemplate",
        stream_id=UUID(payload.get("template_id", str(uuid4()))),
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        principal_id=principal_id,
    )


@pytest.mark.unit
async def test_apply_on_unsubscribed_event_type_is_noop() -> None:
    """Defensive: foreign event types leak through to apply() without
    emitting SQL. The worker should filter by subscribed_event_types, but
    we don't blow up if it doesn't."""
    proj = ClearanceTemplateSummaryProjection()
    conn = _RecordingConn()
    await proj.apply(
        _stored(
            "ForeignEventType",
            {"template_id": str(uuid4()), "occurred_at": _NOW.isoformat()},
        ),
        conn,  # type: ignore[arg-type]
    )
    assert conn.calls == []


@pytest.mark.unit
async def test_apply_clearance_template_activated_updates_status_to_active() -> None:
    """ClearanceTemplateActivated emits UPDATE setting status='Active'."""
    proj = ClearanceTemplateSummaryProjection()
    conn = _RecordingConn()
    tid = uuid4()
    actor = uuid4()
    await proj.apply(
        _stored(
            "ClearanceTemplateActivated",
            {
                "template_id": str(tid),
                "occurred_at": _NOW.isoformat(),
                "activated_by": str(actor),
            },
        ),
        conn,  # type: ignore[arg-type]
    )
    assert len(conn.calls) == 1
    sql, args = conn.calls[0]
    assert "UPDATE proj_safety_clearance_template_summary" in sql
    assert "status = $2" in sql
    assert args[0] == tid
    assert args[1] == "Active"


@pytest.mark.unit
async def test_apply_clearance_template_versioned_updates_version_and_supersedes() -> None:
    """ClearanceTemplateVersioned emits UPDATE with new_version + supersedes_template_id."""
    proj = ClearanceTemplateSummaryProjection()
    conn = _RecordingConn()
    tid = uuid4()
    parent_tid = uuid4()
    actor = uuid4()
    await proj.apply(
        _stored(
            "ClearanceTemplateVersioned",
            {
                "template_id": str(tid),
                "new_version": 2,
                "supersedes_template_id": str(parent_tid),
                "occurred_at": _NOW.isoformat(),
                "versioned_by": str(actor),
            },
        ),
        conn,  # type: ignore[arg-type]
    )
    assert len(conn.calls) == 1
    sql, args = conn.calls[0]
    assert "UPDATE proj_safety_clearance_template_summary" in sql
    assert "version = $2" in sql
    assert "supersedes_template_id = $3" in sql
    assert args[0] == tid
    assert args[1] == 2
    assert args[2] == parent_tid


@pytest.mark.unit
async def test_apply_clearance_template_deprecated_updates_status_to_deprecated() -> None:
    """ClearanceTemplateDeprecated emits UPDATE setting status='Deprecated'."""
    proj = ClearanceTemplateSummaryProjection()
    conn = _RecordingConn()
    tid = uuid4()
    actor = uuid4()
    await proj.apply(
        _stored(
            "ClearanceTemplateDeprecated",
            {
                "template_id": str(tid),
                "occurred_at": _NOW.isoformat(),
                "deprecated_by": str(actor),
            },
        ),
        conn,  # type: ignore[arg-type]
    )
    assert len(conn.calls) == 1
    sql, args = conn.calls[0]
    assert "UPDATE proj_safety_clearance_template_summary" in sql
    assert "status = $2" in sql
    assert args[0] == tid
    assert args[1] == "Deprecated"


@pytest.mark.unit
async def test_apply_clearance_template_withdrawn_updates_status_to_withdrawn() -> None:
    """ClearanceTemplateWithdrawn emits UPDATE setting status='Withdrawn'."""
    proj = ClearanceTemplateSummaryProjection()
    conn = _RecordingConn()
    tid = uuid4()
    actor = uuid4()
    await proj.apply(
        _stored(
            "ClearanceTemplateWithdrawn",
            {
                "template_id": str(tid),
                "occurred_at": _NOW.isoformat(),
                "withdrawn_by": str(actor),
            },
        ),
        conn,  # type: ignore[arg-type]
    )
    assert len(conn.calls) == 1
    sql, args = conn.calls[0]
    assert "UPDATE proj_safety_clearance_template_summary" in sql
    assert "status = $2" in sql
    assert args[0] == tid
    assert args[1] == "Withdrawn"
