"""Unit tests for `ClearanceSummaryProjection`.

Covers:
  - `split_binding_ids` helper (5-arm binding split into 4 typed lists)
  - `apply()` dispatch for each event type (using a recording fake conn)
  - `ClearanceReviewStepAppended` is subscribed-but-no-op (no SQL emitted)
  - Unsubscribed event types are silently ignored (defensive)
  - subscribed_event_types matches the 7 events the projection cares about
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.safety.projections import ClearanceSummaryProjection
from cora.safety.projections.clearance import split_binding_ids

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)


# ---------- split_binding_ids ----------


@pytest.mark.unit
def test_split_binding_ids_pivots_typed_arms_into_four_lists() -> None:
    sid, aid, rid, pid = uuid4(), uuid4(), uuid4(), uuid4()
    bindings: list[dict[str, Any]] = [
        {"kind": "Subject", "id": str(sid)},
        {"kind": "Asset", "id": str(aid)},
        {"kind": "Run", "id": str(rid)},
        {"kind": "Procedure", "id": str(pid)},
    ]
    subject_ids, asset_ids, run_ids, procedure_ids = split_binding_ids(bindings)
    assert subject_ids == [sid]
    assert asset_ids == [aid]
    assert run_ids == [rid]
    assert procedure_ids == [pid]


@pytest.mark.unit
def test_split_binding_ids_skips_external_bindings() -> None:
    """ExternalRefBinding refs are anti-corruption refs, not projected."""
    sid = uuid4()
    bindings: list[dict[str, Any]] = [
        {"kind": "Subject", "id": str(sid)},
        {"kind": "External", "scheme": "proposal", "value": "GUP-12345"},
        {"kind": "External", "scheme": "btr", "value": "BTR-67890"},
    ]
    subject_ids, asset_ids, run_ids, procedure_ids = split_binding_ids(bindings)
    assert subject_ids == [sid]
    assert asset_ids == []
    assert run_ids == []
    assert procedure_ids == []


@pytest.mark.unit
def test_split_binding_ids_empty_list_returns_four_empty_lists() -> None:
    result = split_binding_ids([])
    assert result == ([], [], [], [])


@pytest.mark.unit
def test_split_binding_ids_handles_multiple_per_kind() -> None:
    sids = [uuid4() for _ in range(3)]
    bindings: list[dict[str, Any]] = [{"kind": "Subject", "id": str(sid)} for sid in sids]
    subject_ids, _, _, _ = split_binding_ids(bindings)
    assert subject_ids == sids


# ---------- subscribed_event_types lock ----------


@pytest.mark.unit
def test_subscribed_event_types_covers_all_9_clearance_events() -> None:
    """Projection MUST subscribe to every event the worker should deliver,
    even no-op ones (per the architecture invariant)."""
    proj = ClearanceSummaryProjection()
    assert proj.subscribed_event_types == frozenset(
        {
            "ClearanceRegistered",
            "ClearanceSubmitted",
            "ClearanceReviewStarted",
            "ClearanceReviewStepAppended",
            "ClearanceApproved",
            "ClearanceRejected",
            "ClearanceActivated",
            "ClearanceExpired",
            "ClearanceSuperseded",
        }
    )


@pytest.mark.unit
def test_projection_name_locked() -> None:
    """Name is the projection-bookmark key + the migration table name; must not drift."""
    assert ClearanceSummaryProjection.name == "proj_safety_clearance_summary"


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
        stream_type="Clearance",
        stream_id=UUID(payload.get("clearance_id", str(uuid4()))),
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
async def test_apply_clearance_registered_emits_insert() -> None:
    proj = ClearanceSummaryProjection()
    conn = _RecordingConn()
    cid = uuid4()
    fid = uuid4()
    sid = uuid4()
    await proj.apply(
        _stored(
            "ClearanceRegistered",
            {
                "clearance_id": str(cid),
                "kind": "ESAF",
                "facility_asset_id": str(fid),
                "title": "Pilot",
                "external_id": None,
                "risk_band": None,
                "bindings": [{"kind": "Subject", "id": str(sid)}],
                "declarations": [],
                "valid_from": None,
                "valid_until": None,
                "parent_id": None,
                "occurred_at": _NOW.isoformat(),
            },
        ),
        conn,  # type: ignore[arg-type]
    )
    assert len(conn.calls) == 1
    sql, args = conn.calls[0]
    assert "INSERT INTO proj_safety_clearance_summary" in sql
    assert args[0] == cid
    assert args[1] == "ESAF"
    assert args[2] == fid
    assert args[6] == [sid]  # subject_binding_ids


@pytest.mark.unit
async def test_apply_clearance_review_step_recorded_is_no_op() -> None:
    """Subscribed-but-no-op: chain lives on aggregate stream only.

    The architecture invariant requires the projection to subscribe to
    every event the worker may deliver (so bookmarks advance correctly).
    No SQL should be emitted for this event type.
    """
    proj = ClearanceSummaryProjection()
    conn = _RecordingConn()
    await proj.apply(
        _stored(
            "ClearanceReviewStepAppended",
            {
                "clearance_id": str(uuid4()),
                "step_index": 0,
                "role": "BeamlineScientist",
                "decided_by": str(uuid4()),
                "decision": "Approved",
                "decided_at": _NOW.isoformat(),
                "notes": None,
                "occurred_at": _NOW.isoformat(),
            },
        ),
        conn,  # type: ignore[arg-type]
    )
    assert conn.calls == []


@pytest.mark.unit
async def test_apply_unsubscribed_event_type_is_silently_ignored() -> None:
    """Defensive: even if a foreign event reaches apply, it's a no-op
    (the worker should filter by subscribed_event_types, but we don't
    blow up if it leaks)."""
    proj = ClearanceSummaryProjection()
    conn = _RecordingConn()
    await proj.apply(
        _stored(
            "SomeOtherBcEvent",
            {"clearance_id": str(uuid4()), "occurred_at": _NOW.isoformat()},
        ),
        conn,  # type: ignore[arg-type]
    )
    assert conn.calls == []


@pytest.mark.unit
async def test_apply_clearance_approved_includes_validity_window_overrides() -> None:
    """Approved emits UPDATE with status + last_status_changed_at +
    last_reviewed_by (read from envelope) + COALESCE(valid_from,
    valid_until)."""
    proj = ClearanceSummaryProjection()
    conn = _RecordingConn()
    cid = uuid4()
    actor = uuid4()
    valid_from = datetime(2026, 6, 1, tzinfo=UTC)
    valid_until = datetime(2026, 9, 1, tzinfo=UTC)
    await proj.apply(
        _stored(
            "ClearanceApproved",
            {
                "clearance_id": str(cid),
                "valid_from": valid_from.isoformat(),
                "valid_until": valid_until.isoformat(),
                "occurred_at": _NOW.isoformat(),
            },
            principal_id=actor,
        ),
        conn,  # type: ignore[arg-type]
    )
    sql, args = conn.calls[0]
    assert "status = 'Approved'" in sql
    assert args[0] == cid
    assert args[2] == actor
    assert args[3] == valid_from
    assert args[4] == valid_until


@pytest.mark.unit
async def test_apply_clearance_rejected_includes_reason_and_actor_from_envelope() -> None:
    """Rejected emits UPDATE; rejecting actor read from envelope (not payload)."""
    proj = ClearanceSummaryProjection()
    conn = _RecordingConn()
    cid = uuid4()
    actor = uuid4()
    await proj.apply(
        _stored(
            "ClearanceRejected",
            {
                "clearance_id": str(cid),
                "reason": "ESRB found insufficient PPE specification",
                "occurred_at": _NOW.isoformat(),
            },
            principal_id=actor,
        ),
        conn,  # type: ignore[arg-type]
    )
    sql, args = conn.calls[0]
    assert "status = 'Rejected'" in sql
    assert args[0] == cid
    assert args[2] == "ESRB found insufficient PPE specification"
    assert args[3] == actor


@pytest.mark.unit
async def test_apply_clearance_submitted_emits_status_update() -> None:
    """Submitted emits UPDATE status='Submitted' + last_status_changed_at."""
    proj = ClearanceSummaryProjection()
    conn = _RecordingConn()
    cid = uuid4()
    await proj.apply(
        _stored(
            "ClearanceSubmitted",
            {"clearance_id": str(cid), "occurred_at": _NOW.isoformat()},
        ),
        conn,  # type: ignore[arg-type]
    )
    sql, args = conn.calls[0]
    assert "status = 'Submitted'" in sql
    assert args[0] == cid
    assert args[1] == _NOW


@pytest.mark.unit
async def test_apply_clearance_review_started_emits_under_review_update() -> None:
    """ClearanceReviewStarted writes status='UnderReview' (the FSM state
    name) -- the event-name / status-name asymmetry is deliberate per
    11a-c-1 rename. Pin both to catch accidental drift."""
    proj = ClearanceSummaryProjection()
    conn = _RecordingConn()
    cid = uuid4()
    await proj.apply(
        _stored(
            "ClearanceReviewStarted",
            {
                "clearance_id": str(cid),
                "first_reviewer_role": "BeamlineScientist",
                "occurred_at": _NOW.isoformat(),
            },
        ),
        conn,  # type: ignore[arg-type]
    )
    sql, args = conn.calls[0]
    assert "status = 'UnderReview'" in sql
    assert args[0] == cid


@pytest.mark.unit
async def test_apply_clearance_activated_emits_active_update() -> None:
    """Activated transitions Approved -> Active."""
    proj = ClearanceSummaryProjection()
    conn = _RecordingConn()
    cid = uuid4()
    await proj.apply(
        _stored(
            "ClearanceActivated",
            {"clearance_id": str(cid), "occurred_at": _NOW.isoformat()},
        ),
        conn,  # type: ignore[arg-type]
    )
    sql, args = conn.calls[0]
    assert "status = 'Active'" in sql
    assert args[0] == cid


@pytest.mark.unit
async def test_apply_clearance_expired_includes_reason() -> None:
    """Expired emits UPDATE status='Expired' + last_status_reason."""
    proj = ClearanceSummaryProjection()
    conn = _RecordingConn()
    cid = uuid4()
    await proj.apply(
        _stored(
            "ClearanceExpired",
            {
                "clearance_id": str(cid),
                "reason": "validity window elapsed",
                "occurred_at": _NOW.isoformat(),
            },
        ),
        conn,  # type: ignore[arg-type]
    )
    sql, args = conn.calls[0]
    assert "status = 'Expired'" in sql
    assert args[0] == cid
    assert args[1] == _NOW
    assert args[2] == "validity window elapsed"


@pytest.mark.unit
async def test_apply_clearance_superseded_emits_status_only() -> None:
    """Superseded emits UPDATE status='Superseded'. The payload's
    `by_clearance_id` is deliberately NOT projected today (parent->child
    denorm column deferred until a list-view consumer asks for it).
    This test pins the deferred state so an accidental SQL change that
    surfaced by_clearance_id would fail loudly."""
    proj = ClearanceSummaryProjection()
    conn = _RecordingConn()
    cid = uuid4()
    by_cid = uuid4()
    await proj.apply(
        _stored(
            "ClearanceSuperseded",
            {
                "clearance_id": str(cid),
                "by_clearance_id": str(by_cid),
                "occurred_at": _NOW.isoformat(),
            },
        ),
        conn,  # type: ignore[arg-type]
    )
    sql, args = conn.calls[0]
    assert "status = 'Superseded'" in sql
    assert args[0] == cid
    assert args[1] == _NOW
    # by_clearance_id NOT in args list -- column not added to projection today
    assert str(by_cid) not in (str(a) for a in args)
