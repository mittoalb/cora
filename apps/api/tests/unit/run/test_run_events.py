"""Unit tests for the Run aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.run.aggregates.run.events import (
    RunAborted,
    RunCompleted,
    RunHeld,
    RunResumed,
    RunStarted,
    RunStopped,
    event_type_name,
    from_stored,
    to_payload,
)

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _stored(
    event_type: str,
    payload: dict[str, object],
    *,
    stream_id: object | None = None,
) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Run",
        stream_id=stream_id or uuid4(),  # type: ignore[arg-type]
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
def test_event_type_name_returns_class_name() -> None:
    event = RunStarted(
        run_id=uuid4(),
        name="X",
        plan_id=uuid4(),
        subject_id=uuid4(),
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "RunStarted"


@pytest.mark.unit
def test_to_payload_serializes_run_started_with_subject_to_primitives() -> None:
    run_id = uuid4()
    plan_id = uuid4()
    subject_id = uuid4()
    event = RunStarted(
        run_id=run_id,
        name="32-ID FlyScan",
        plan_id=plan_id,
        subject_id=subject_id,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "run_id": str(run_id),
        "name": "32-ID FlyScan",
        "plan_id": str(plan_id),
        "subject_id": str(subject_id),
        "raid": None,
        # 6g-c additive payload fields default to {} / None when not
        # supplied; pre-6g-c stored events stay forward-compat via
        # `payload.get(..., default)` in `from_stored`.
        "override_parameters": {},
        "effective_parameters": {},
        "triggered_by": None,
        # 11a-c-3 additive payload field for ExternalRef-based
        # clearance coverage (anti-corruption refs to proposal /
        # btr / lab_visit / session). Defaults to [] when omitted;
        # forward-compat via `payload.get("external_refs", [])`.
        "external_refs": [],
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_run_started_without_subject_as_null() -> None:
    """Dark-field / calibration runs have subject_id=None — must
    serialize as JSON null (not the string 'None')."""
    run_id = uuid4()
    plan_id = uuid4()
    event = RunStarted(
        run_id=run_id,
        name="Dark field calibration",
        plan_id=plan_id,
        subject_id=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["subject_id"] is None


@pytest.mark.unit
def test_to_payload_serializes_run_started_with_raid() -> None:
    """7d retrofit: raid carries verbatim through the payload."""
    event = RunStarted(
        run_id=uuid4(),
        name="32-ID FlyScan",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        raid="https://raid.org/10.7935/cora-test-raid",
    )
    assert to_payload(event)["raid"] == "https://raid.org/10.7935/cora-test-raid"


@pytest.mark.unit
def test_to_payload_serializes_run_started_with_6gc_parameter_fields() -> None:
    """Phase 6g-c additive payload: override_parameters,
    effective_parameters, triggered_by carry verbatim through the
    payload."""
    overrides = {"energy_kev": 12.0}
    effective = {"energy_kev": 12.0, "exposure_ms": 100}
    event = RunStarted(
        run_id=uuid4(),
        name="32-ID FlyScan",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        override_parameters=overrides,
        effective_parameters=effective,
        triggered_by="operator:opid:5",
    )
    payload = to_payload(event)
    assert payload["override_parameters"] == overrides
    assert payload["effective_parameters"] == effective
    assert payload["triggered_by"] == "operator:opid:5"


@pytest.mark.unit
def test_to_payload_serializes_6gc_fields_with_defaults() -> None:
    """Default empty dicts and None triggered_by serialize as `{}` /
    null (NOT omitted). Pinned because the projection's
    `bool(payload.get("override_parameters"))` test relies on the
    key being present."""
    event = RunStarted(
        run_id=uuid4(),
        name="32-ID FlyScan",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["override_parameters"] == {}
    assert payload["effective_parameters"] == {}
    assert payload["triggered_by"] is None


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_without_6gc_keys_as_defaults() -> None:
    """Forward-compatible load: pre-6g-c events have no
    override_parameters/effective_parameters/triggered_by keys in
    jsonb. from_stored returns the field defaults for those, keeping
    older streams replayable. Mirrors the raid forward-compat pattern."""
    run_id = uuid4()
    plan_id = uuid4()
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "Pre-6g-c run",
            "plan_id": str(plan_id),
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
            # NOTE: no override_parameters, effective_parameters, or
            # triggered_by keys — this is what pre-6g-c events look like.
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunStarted)
    assert event.override_parameters == {}
    assert event.effective_parameters == {}
    assert event.triggered_by is None


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_with_6gc_keys() -> None:
    """Post-6g-c events round-trip with parameter values intact."""
    run_id = uuid4()
    plan_id = uuid4()
    overrides = {"energy_kev": 12.0}
    effective = {"energy_kev": 12.0, "exposure_ms": 100}
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "Post-6g-c run",
            "plan_id": str(plan_id),
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
            "override_parameters": overrides,
            "effective_parameters": effective,
            "triggered_by": "operator:opid:5",
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunStarted)
    assert event.override_parameters == overrides
    assert event.effective_parameters == effective
    assert event.triggered_by == "operator:opid:5"


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_without_raid_key_as_none() -> None:
    """Forward-compatible load: pre-7d events have no raid key in
    jsonb. from_stored returns raid=None for those, keeping older
    streams replayable."""
    run_id = uuid4()
    plan_id = uuid4()
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "Dark field calibration",
            "plan_id": str(plan_id),
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
            # NOTE: no "raid" key — this is what pre-7d events look like.
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunStarted)
    assert event.raid is None


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_with_raid_key() -> None:
    run_id = uuid4()
    plan_id = uuid4()
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "32-ID FlyScan",
            "plan_id": str(plan_id),
            "subject_id": None,
            "raid": "https://raid.org/10.7935/cora-test-raid",
            "occurred_at": _NOW.isoformat(),
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunStarted)
    assert event.raid == "https://raid.org/10.7935/cora-test-raid"


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_with_subject() -> None:
    run_id = uuid4()
    plan_id = uuid4()
    subject_id = uuid4()
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "32-ID FlyScan",
            "plan_id": str(plan_id),
            "subject_id": str(subject_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == RunStarted(
        run_id=run_id,
        name="32-ID FlyScan",
        plan_id=plan_id,
        subject_id=subject_id,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_without_subject() -> None:
    """JSON null deserializes to Python None for subject_id."""
    run_id = uuid4()
    plan_id = uuid4()
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "Dark field",
            "plan_id": str(plan_id),
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, RunStarted)
    assert rebuilt.subject_id is None


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net for Run events."""
    original = RunStarted(
        run_id=uuid4(),
        name="X",
        plan_id=uuid4(),
        subject_id=uuid4(),
        occurred_at=_NOW,
    )
    stored = _stored("RunStarted", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    stored = _stored("PlanDefined", {})
    with pytest.raises(ValueError, match="Unknown RunEvent event_type"):
        from_stored(stored)


# ---------- RunCompleted (6f-2) ----------


@pytest.mark.unit
def test_event_type_name_for_run_completed() -> None:
    event = RunCompleted(run_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "RunCompleted"


@pytest.mark.unit
def test_to_payload_serializes_run_completed_to_primitives() -> None:
    run_id = uuid4()
    event = RunCompleted(run_id=run_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "run_id": str(run_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_run_completed() -> None:
    run_id = uuid4()
    stored = _stored(
        "RunCompleted",
        {
            "run_id": str(run_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == RunCompleted(run_id=run_id, occurred_at=_NOW)


@pytest.mark.unit
def test_run_completed_round_trips() -> None:
    original = RunCompleted(run_id=uuid4(), occurred_at=_NOW)
    stored = _stored("RunCompleted", to_payload(original))
    assert from_stored(stored) == original


# ---------- RunAborted (6f-2) ----------


@pytest.mark.unit
def test_event_type_name_for_run_aborted() -> None:
    event = RunAborted(run_id=uuid4(), reason="X", occurred_at=_NOW)
    assert event_type_name(event) == "RunAborted"


@pytest.mark.unit
def test_to_payload_serializes_run_aborted_to_primitives() -> None:
    run_id = uuid4()
    event = RunAborted(run_id=run_id, reason="detector overheating", occurred_at=_NOW)
    assert to_payload(event) == {
        "run_id": str(run_id),
        "reason": "detector overheating",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_run_aborted() -> None:
    run_id = uuid4()
    stored = _stored(
        "RunAborted",
        {
            "run_id": str(run_id),
            "reason": "operator stop",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == RunAborted(
        run_id=run_id,
        reason="operator stop",
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_run_aborted_round_trips() -> None:
    original = RunAborted(
        run_id=uuid4(),
        reason="beam dump unscheduled",
        occurred_at=_NOW,
    )
    stored = _stored("RunAborted", to_payload(original))
    assert from_stored(stored) == original


# ---------- RunHeld (6f-3) ----------


@pytest.mark.unit
def test_event_type_name_for_run_held() -> None:
    event = RunHeld(run_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "RunHeld"


@pytest.mark.unit
def test_to_payload_serializes_run_held_to_primitives() -> None:
    run_id = uuid4()
    event = RunHeld(run_id=run_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "run_id": str(run_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_run_held() -> None:
    run_id = uuid4()
    stored = _stored(
        "RunHeld",
        {
            "run_id": str(run_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == RunHeld(run_id=run_id, occurred_at=_NOW)


@pytest.mark.unit
def test_run_held_round_trips() -> None:
    original = RunHeld(run_id=uuid4(), occurred_at=_NOW)
    stored = _stored("RunHeld", to_payload(original))
    assert from_stored(stored) == original


# ---------- RunResumed (6f-3) ----------


@pytest.mark.unit
def test_event_type_name_for_run_resumed() -> None:
    event = RunResumed(run_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "RunResumed"


@pytest.mark.unit
def test_to_payload_serializes_run_resumed_to_primitives() -> None:
    run_id = uuid4()
    event = RunResumed(run_id=run_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "run_id": str(run_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_run_resumed() -> None:
    run_id = uuid4()
    stored = _stored(
        "RunResumed",
        {
            "run_id": str(run_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == RunResumed(run_id=run_id, occurred_at=_NOW)


@pytest.mark.unit
def test_run_resumed_round_trips() -> None:
    original = RunResumed(run_id=uuid4(), occurred_at=_NOW)
    stored = _stored("RunResumed", to_payload(original))
    assert from_stored(stored) == original


# ---------- RunStopped (6f-3) ----------


@pytest.mark.unit
def test_event_type_name_for_run_stopped() -> None:
    event = RunStopped(run_id=uuid4(), reason="X", occurred_at=_NOW)
    assert event_type_name(event) == "RunStopped"


@pytest.mark.unit
def test_to_payload_serializes_run_stopped_to_primitives() -> None:
    run_id = uuid4()
    event = RunStopped(run_id=run_id, reason="hit time budget cleanly", occurred_at=_NOW)
    assert to_payload(event) == {
        "run_id": str(run_id),
        "reason": "hit time budget cleanly",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_run_stopped() -> None:
    run_id = uuid4()
    stored = _stored(
        "RunStopped",
        {
            "run_id": str(run_id),
            "reason": "operator stop",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == RunStopped(
        run_id=run_id,
        reason="operator stop",
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_run_stopped_round_trips() -> None:
    original = RunStopped(
        run_id=uuid4(),
        reason="hit time budget cleanly",
        occurred_at=_NOW,
    )
    stored = _stored("RunStopped", to_payload(original))
    assert from_stored(stored) == original


# ---------- RunReadingLogbookOpened (6f-5b) ----------

from cora.run.aggregates.run import (  # noqa: E402
    LOGBOOK_KIND_READING,
    READING_LOGBOOK_SCHEMA,
)
from cora.run.aggregates.run.events import RunReadingLogbookOpened  # noqa: E402


@pytest.mark.unit
def test_event_type_name_for_run_reading_logbook_opened() -> None:
    event = RunReadingLogbookOpened(
        run_id=uuid4(),
        logbook_id=uuid4(),
        kind=LOGBOOK_KIND_READING,
        schema=READING_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "RunReadingLogbookOpened"


@pytest.mark.unit
def test_to_payload_serializes_run_reading_logbook_opened_to_primitives() -> None:
    """Schema flattens via LogbookSchema.to_dict for jsonb storage."""
    run_id = uuid4()
    logbook_id = uuid4()
    event = RunReadingLogbookOpened(
        run_id=run_id,
        logbook_id=logbook_id,
        kind=LOGBOOK_KIND_READING,
        schema=READING_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["run_id"] == str(run_id)
    assert payload["logbook_id"] == str(logbook_id)
    assert payload["kind"] == LOGBOOK_KIND_READING
    assert payload["occurred_at"] == _NOW.isoformat()
    # Schema is a nested dict, not the LogbookSchema dataclass.
    assert isinstance(payload["schema"], dict)
    assert "fields" in payload["schema"]


@pytest.mark.unit
def test_from_stored_rebuilds_run_reading_logbook_opened() -> None:
    """Schema rebuilds from the stored dict via LogbookSchema.from_dict."""
    run_id = uuid4()
    logbook_id = uuid4()
    stored = _stored(
        "RunReadingLogbookOpened",
        {
            "run_id": str(run_id),
            "logbook_id": str(logbook_id),
            "kind": LOGBOOK_KIND_READING,
            "schema": READING_LOGBOOK_SCHEMA.to_dict(),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, RunReadingLogbookOpened)
    assert rebuilt.run_id == run_id
    assert rebuilt.logbook_id == logbook_id
    assert rebuilt.kind == LOGBOOK_KIND_READING
    assert rebuilt.schema.fields == READING_LOGBOOK_SCHEMA.fields


@pytest.mark.unit
def test_run_reading_logbook_opened_round_trips() -> None:
    original = RunReadingLogbookOpened(
        run_id=uuid4(),
        logbook_id=uuid4(),
        kind=LOGBOOK_KIND_READING,
        schema=READING_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    stored = _stored("RunReadingLogbookOpened", to_payload(original))
    assert from_stored(stored) == original
