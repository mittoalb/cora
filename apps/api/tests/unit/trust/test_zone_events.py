"""Unit tests for the Zone aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.trust.aggregates.zone.events import (
    ZoneDefined,
    event_type_name,
    from_stored,
    to_payload,
)

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _stored(
    event_type: str,
    payload: dict[str, object],
    *,
    stream_id: object | None = None,
) -> StoredEvent:
    """Build a StoredEvent shell — only event_type + payload are read by from_stored."""
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Zone",
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
    zone_id = uuid4()
    event = ZoneDefined(zone_id=zone_id, name="Detector", occurred_at=_NOW)
    assert event_type_name(event) == "ZoneDefined"


@pytest.mark.unit
def test_to_payload_serializes_zone_defined_to_primitives() -> None:
    zone_id = uuid4()
    event = ZoneDefined(zone_id=zone_id, name="Detector", occurred_at=_NOW)
    assert to_payload(event) == {
        "zone_id": str(zone_id),
        "name": "Detector",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_zone_defined() -> None:
    zone_id = uuid4()
    stored = _stored(
        "ZoneDefined",
        {
            "zone_id": str(zone_id),
            "name": "Detector",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == ZoneDefined(zone_id=zone_id, name="Detector", occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net: the (de)serialization pair must be each other's inverse."""
    zone_id = uuid4()
    original = ZoneDefined(zone_id=zone_id, name="Detector", occurred_at=_NOW)
    stored = _stored("ZoneDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped.

    Note: per CONTRIBUTING.md the routing key for cross-BC subscribers
    is `(stream_type, event_type)` rather than event_type alone, so
    name collisions across BCs (e.g. a hypothetical "Defined" emitted
    by another aggregate) won't actually reach this evolver — but the
    loud-failure here is the per-stream safety net regardless.
    """
    stored = _stored("ActorRegistered", {})
    with pytest.raises(ValueError, match="Unknown ZoneEvent event_type"):
        from_stored(stored)


# `to_new_event` envelope construction lives at
# `cora.infrastructure.event_envelope` and is covered by
# `tests/unit/test_event_envelope.py`. Handler-level tests
# (`test_define_zone_handler`, integration / contract tests) verify
# the envelope shape end-to-end against a real event store.


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "ZoneDefined",
    ],
)
def test_from_stored_raises_on_malformed_payload(event_type: str) -> None:
    """Per the convention adopted post-corpus-survey (Marten /
    pyeventsourcing / Pydantic / msgspec all wrap), each event-type case
    wraps `KeyError`/`TypeError`/`AttributeError` into a tagged
    `ValueError` so a corrupted event row fails loud with the event-type
    name in the message rather than bubbling a raw KeyError from deep
    in the load path."""
    with pytest.raises(ValueError, match=f"Malformed {event_type} payload"):
        from_stored(_stored(event_type, {}))
