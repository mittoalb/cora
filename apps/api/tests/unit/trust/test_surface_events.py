"""SurfaceDefined event payload round-trip + event_type_name pinning."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.trust.aggregates.surface import (
    SurfaceDefined,
    SurfaceKind,
    event_type_name,
    from_stored,
    to_payload,
)

_NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_event_type_name_pins_class_name() -> None:
    """The discriminator string written into StoredEvent.event_type
    MUST equal the class name — projections + integration tests
    filter events by this string."""
    event = SurfaceDefined(
        surface_id=uuid4(),
        name="X",
        kind=SurfaceKind.HTTP,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "SurfaceDefined"


@pytest.mark.unit
def test_to_payload_serializes_to_primitives() -> None:
    surface_id = uuid4()
    event = SurfaceDefined(
        surface_id=surface_id,
        name="System HTTP",
        kind=SurfaceKind.HTTP,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "surface_id": str(surface_id),
        "name": "System HTTP",
        "kind": "http",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_payload_round_trip_via_from_stored() -> None:
    surface_id = uuid4()
    event = SurfaceDefined(
        surface_id=surface_id,
        name="System MCP stdio",
        kind=SurfaceKind.MCP_STDIO,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    stored = StoredEvent(
        event_id=uuid4(),
        stream_type="Surface",
        stream_id=surface_id,
        version=1,
        event_type="SurfaceDefined",
        schema_version=1,
        payload=payload,
        metadata={},
        correlation_id=uuid4(),
        causation_id=None,
        principal_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        position=1,
    )
    rebuilt = from_stored(stored)
    assert rebuilt == event


@pytest.mark.unit
def test_from_stored_rejects_unknown_event_type() -> None:
    """A future event type added to SurfaceEvent without updating
    from_stored fails loud at fold time, not at fitness-test time."""
    stored = StoredEvent(
        event_id=uuid4(),
        stream_type="Surface",
        stream_id=uuid4(),
        version=1,
        event_type="SurfaceFooBared",  # not a real event type
        schema_version=1,
        payload={},
        metadata={},
        correlation_id=uuid4(),
        causation_id=None,
        principal_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        position=1,
    )
    with pytest.raises(ValueError, match="Unknown SurfaceEvent"):
        from_stored(stored)


@pytest.mark.unit
def test_from_stored_rejects_malformed_payload() -> None:
    """Missing required key surfaces a clear ValueError, not KeyError."""
    stored = StoredEvent(
        event_id=uuid4(),
        stream_type="Surface",
        stream_id=uuid4(),
        version=1,
        event_type="SurfaceDefined",
        schema_version=1,
        payload={"surface_id": str(uuid4()), "kind": "http"},  # missing name + occurred_at
        metadata={},
        correlation_id=uuid4(),
        causation_id=None,
        principal_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        position=1,
    )
    with pytest.raises(ValueError, match="Malformed SurfaceDefined payload"):
        from_stored(stored)


@pytest.mark.unit
def test_from_stored_rejects_unknown_kind_string() -> None:
    """Closed enum: a payload claiming kind='a2a' (deferred) fails fold
    instead of silently degrading."""
    stored = StoredEvent(
        event_id=uuid4(),
        stream_type="Surface",
        stream_id=uuid4(),
        version=1,
        event_type="SurfaceDefined",
        schema_version=1,
        payload={
            "surface_id": str(uuid4()),
            "name": "Future A2A",
            "kind": "a2a",  # not yet in SurfaceKind
            "occurred_at": _NOW.isoformat(),
        },
        metadata={},
        correlation_id=uuid4(),
        causation_id=None,
        principal_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        position=1,
    )
    with pytest.raises(ValueError, match="Malformed SurfaceDefined payload"):
        from_stored(stored)
