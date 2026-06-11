"""Unit tests for ClearanceTemplate aggregate event serialization."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateDefined,
    event_type_name,
    from_stored,
    to_payload,
)

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_TEMPLATE_ID = uuid4()
_DEFINED_BY = uuid4()


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    """Build a StoredEvent shell  --  only event_type + payload are read by from_stored."""
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="ClearanceTemplate",
        stream_id=_TEMPLATE_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


# ---------- ClearanceTemplateDefined ----------


@pytest.mark.unit
def test_event_type_name_returns_clearance_template_defined() -> None:
    event = ClearanceTemplateDefined(
        template_id=_TEMPLATE_ID,
        facility_code="aps",
        code="ESAF-v1",
        title="Experiment Safety Assessment Form",
        occurred_at=_NOW,
        defined_by=_DEFINED_BY,
    )
    assert event_type_name(event) == "ClearanceTemplateDefined"


@pytest.mark.unit
def test_to_payload_serializes_clearance_template_defined() -> None:
    event = ClearanceTemplateDefined(
        template_id=_TEMPLATE_ID,
        facility_code="aps",
        code="ESAF-v1",
        title="Experiment Safety Assessment Form",
        version=1,
        supersedes_template_id=None,
        external_ref=None,
        occurred_at=_NOW,
        defined_by=_DEFINED_BY,
    )
    payload = to_payload(event)
    assert payload["template_id"] == str(_TEMPLATE_ID)
    assert payload["facility_code"] == "aps"
    assert payload["code"] == "ESAF-v1"
    assert payload["title"] == "Experiment Safety Assessment Form"
    assert payload["version"] == 1
    assert payload["supersedes_template_id"] is None
    assert payload["external_ref"] is None
    assert payload["occurred_at"] == _NOW.isoformat()
    assert payload["defined_by"] == str(_DEFINED_BY)


@pytest.mark.unit
def test_to_payload_includes_version_and_supersedes() -> None:
    """Version + supersedes_template_id are carried in day-one payloads."""
    prev_template_id = uuid4()
    event = ClearanceTemplateDefined(
        template_id=_TEMPLATE_ID,
        facility_code="aps",
        code="ESAF-v1",
        title="Experiment Safety Assessment Form",
        version=2,
        supersedes_template_id=prev_template_id,
        external_ref="EXTERNAL-123",
        occurred_at=_NOW,
        defined_by=_DEFINED_BY,
    )
    payload = to_payload(event)
    assert payload["version"] == 2
    assert payload["supersedes_template_id"] == str(prev_template_id)
    assert payload["external_ref"] == "EXTERNAL-123"


@pytest.mark.unit
def test_from_stored_rebuilds_clearance_template_defined() -> None:
    stored = _stored(
        "ClearanceTemplateDefined",
        {
            "template_id": str(_TEMPLATE_ID),
            "facility_code": "aps",
            "code": "ESAF-v1",
            "title": "Experiment Safety Assessment Form",
            "version": 1,
            "supersedes_template_id": None,
            "external_ref": None,
            "occurred_at": _NOW.isoformat(),
            "defined_by": str(_DEFINED_BY),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == ClearanceTemplateDefined(
        template_id=_TEMPLATE_ID,
        facility_code="aps",
        code="ESAF-v1",
        title="Experiment Safety Assessment Form",
        version=1,
        supersedes_template_id=None,
        external_ref=None,
        occurred_at=_NOW,
        defined_by=_DEFINED_BY,
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net: serialization pair must be each other's inverse."""
    original = ClearanceTemplateDefined(
        template_id=_TEMPLATE_ID,
        facility_code="aps",
        code="ESAF-v1",
        title="Experiment Safety Assessment Form",
        version=1,
        supersedes_template_id=None,
        external_ref=None,
        occurred_at=_NOW,
        defined_by=_DEFINED_BY,
    )
    stored = _stored("ClearanceTemplateDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event types must fail loud, not be silently dropped."""
    stored = _stored("UnknownEvent", {})
    with pytest.raises(ValueError, match="Unknown ClearanceTemplateEvent event_type"):
        from_stored(stored)
