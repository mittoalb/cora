"""Unit tests for the Conduit aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.channel import ChannelFieldSpec, ChannelSchema
from cora.infrastructure.ports.event_store import StoredEvent
from cora.trust.aggregates.conduit.events import (
    ConduitChannelClosed,
    ConduitChannelOpened,
    ConduitDefined,
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
        stream_type="Conduit",
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
    event = ConduitDefined(
        conduit_id=uuid4(),
        name="Detector-to-Storage",
        source_zone_id=uuid4(),
        target_zone_id=uuid4(),
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "ConduitDefined"


@pytest.mark.unit
def test_to_payload_serializes_conduit_defined_to_primitives() -> None:
    conduit_id = uuid4()
    source = uuid4()
    target = uuid4()
    event = ConduitDefined(
        conduit_id=conduit_id,
        name="Detector-to-Storage",
        source_zone_id=source,
        target_zone_id=target,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "conduit_id": str(conduit_id),
        "name": "Detector-to-Storage",
        "source_zone_id": str(source),
        "target_zone_id": str(target),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_conduit_defined() -> None:
    conduit_id = uuid4()
    source = uuid4()
    target = uuid4()
    stored = _stored(
        "ConduitDefined",
        {
            "conduit_id": str(conduit_id),
            "name": "Detector-to-Storage",
            "source_zone_id": str(source),
            "target_zone_id": str(target),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == ConduitDefined(
        conduit_id=conduit_id,
        name="Detector-to-Storage",
        source_zone_id=source,
        target_zone_id=target,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net: the (de)serialization pair must be each other's inverse."""
    original = ConduitDefined(
        conduit_id=uuid4(),
        name="Detector-to-Storage",
        source_zone_id=uuid4(),
        target_zone_id=uuid4(),
        occurred_at=_NOW,
    )
    stored = _stored("ConduitDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("ZoneDefined", {})
    with pytest.raises(ValueError, match="Unknown ConduitEvent event_type"):
        from_stored(stored)


# ---------- ConduitChannelOpened (Phase 6f-5a) ----------


def _sample_schema() -> ChannelSchema:
    return ChannelSchema(
        fields={
            "actor_id": ChannelFieldSpec(type="uuid"),
            "command_name": ChannelFieldSpec(type="string"),
        },
        description="auth audit log",
    )


@pytest.mark.unit
def test_event_type_name_for_conduit_channel_opened() -> None:
    event = ConduitChannelOpened(
        conduit_id=uuid4(),
        channel_id=uuid4(),
        kind="traversals",
        schema=_sample_schema(),
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "ConduitChannelOpened"


@pytest.mark.unit
def test_to_payload_serializes_channel_opened_with_schema_dict() -> None:
    conduit_id = uuid4()
    channel_id = uuid4()
    schema = _sample_schema()
    event = ConduitChannelOpened(
        conduit_id=conduit_id,
        channel_id=channel_id,
        kind="traversals",
        schema=schema,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload == {
        "conduit_id": str(conduit_id),
        "channel_id": str(channel_id),
        "kind": "traversals",
        "schema": schema.to_dict(),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_conduit_channel_opened() -> None:
    conduit_id = uuid4()
    channel_id = uuid4()
    schema = _sample_schema()
    stored = _stored(
        "ConduitChannelOpened",
        {
            "conduit_id": str(conduit_id),
            "channel_id": str(channel_id),
            "kind": "traversals",
            "schema": schema.to_dict(),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == ConduitChannelOpened(
        conduit_id=conduit_id,
        channel_id=channel_id,
        kind="traversals",
        schema=schema,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_conduit_channel_opened_round_trips() -> None:
    original = ConduitChannelOpened(
        conduit_id=uuid4(),
        channel_id=uuid4(),
        kind="traversals",
        schema=_sample_schema(),
        occurred_at=_NOW,
    )
    stored = _stored("ConduitChannelOpened", to_payload(original))
    assert from_stored(stored) == original


# ---------- ConduitChannelClosed (Phase 6f-5a) ----------


@pytest.mark.unit
def test_event_type_name_for_conduit_channel_closed() -> None:
    event = ConduitChannelClosed(conduit_id=uuid4(), channel_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "ConduitChannelClosed"


@pytest.mark.unit
def test_to_payload_serializes_channel_closed_to_primitives() -> None:
    conduit_id = uuid4()
    channel_id = uuid4()
    event = ConduitChannelClosed(conduit_id=conduit_id, channel_id=channel_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "conduit_id": str(conduit_id),
        "channel_id": str(channel_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_conduit_channel_closed() -> None:
    conduit_id = uuid4()
    channel_id = uuid4()
    stored = _stored(
        "ConduitChannelClosed",
        {
            "conduit_id": str(conduit_id),
            "channel_id": str(channel_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == ConduitChannelClosed(
        conduit_id=conduit_id, channel_id=channel_id, occurred_at=_NOW
    )


@pytest.mark.unit
def test_conduit_channel_closed_round_trips() -> None:
    original = ConduitChannelClosed(conduit_id=uuid4(), channel_id=uuid4(), occurred_at=_NOW)
    stored = _stored("ConduitChannelClosed", to_payload(original))
    assert from_stored(stored) == original


# `to_new_event` envelope construction lives at
# `cora.infrastructure.event_envelope` and is covered by
# `tests/unit/test_event_envelope.py`. Handler-level tests
# (`test_define_conduit_handler`, integration / contract tests)
# verify the envelope shape end-to-end against a real event store.
