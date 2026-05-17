"""Unit tests for the Actor aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.access.aggregates.actor.events import (
    ActorRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.access.aggregates.actor.state import ActorKind
from cora.infrastructure.ports.event_store import StoredEvent

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)


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
        stream_type="Actor",
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
    actor_id = uuid4()
    event = ActorRegistered(actor_id=actor_id, name="Doga", occurred_at=_NOW, kind=ActorKind.HUMAN)
    assert event_type_name(event) == "ActorRegistered"


@pytest.mark.unit
def test_to_payload_serializes_actor_registered_to_primitives() -> None:
    """Default human-actor payload now carries `kind` per 8f-a additive evolution."""
    actor_id = uuid4()
    event = ActorRegistered(actor_id=actor_id, name="Doga", occurred_at=_NOW, kind=ActorKind.HUMAN)
    assert to_payload(event) == {
        "actor_id": str(actor_id),
        "name": "Doga",
        "occurred_at": _NOW.isoformat(),
        "kind": "human",
    }


@pytest.mark.unit
def test_to_payload_serializes_agent_kind() -> None:
    """ActorRegistered with kind=agent (Phase 8f-a Agent BC co-write) serializes correctly."""
    actor_id = uuid4()
    event = ActorRegistered(
        actor_id=actor_id, name="RunDebrief", occurred_at=_NOW, kind=ActorKind.AGENT
    )
    assert to_payload(event) == {
        "actor_id": str(actor_id),
        "name": "RunDebrief",
        "occurred_at": _NOW.isoformat(),
        "kind": "agent",
    }


@pytest.mark.unit
def test_from_stored_rebuilds_actor_registered_with_kind() -> None:
    """A current-shape payload with `kind` round-trips correctly."""
    actor_id = uuid4()
    stored = _stored(
        "ActorRegistered",
        {
            "actor_id": str(actor_id),
            "name": "Doga",
            "occurred_at": _NOW.isoformat(),
            "kind": "human",
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == ActorRegistered(
        actor_id=actor_id, name="Doga", occurred_at=_NOW, kind=ActorKind.HUMAN
    )


@pytest.mark.unit
def test_from_stored_pre_8f_a_payload_folds_to_human_kind() -> None:
    """Pre-8f-a payloads (no `kind` field) MUST fold to kind=human.

    This is the forward-compat additive-evolution guarantee. Existing
    Actor streams written before 8f-a have payloads without `kind`;
    the evolver supplies the default to keep replay working.
    """
    actor_id = uuid4()
    stored = _stored(
        "ActorRegistered",
        {
            "actor_id": str(actor_id),
            "name": "Doga",
            "occurred_at": _NOW.isoformat(),
            # No "kind" field; pre-8f-a payload shape.
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == ActorRegistered(
        actor_id=actor_id, name="Doga", occurred_at=_NOW, kind=ActorKind.HUMAN
    )


@pytest.mark.unit
def test_from_stored_rebuilds_agent_kind_actor() -> None:
    """An agent-kind Actor (Phase 8f-a Agent BC co-write) replays correctly."""
    actor_id = uuid4()
    stored = _stored(
        "ActorRegistered",
        {
            "actor_id": str(actor_id),
            "name": "RunDebrief",
            "occurred_at": _NOW.isoformat(),
            "kind": "agent",
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == ActorRegistered(
        actor_id=actor_id, name="RunDebrief", occurred_at=_NOW, kind=ActorKind.AGENT
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net: the (de)serialization pair must be each other's inverse."""
    actor_id = uuid4()
    original = ActorRegistered(
        actor_id=actor_id, name="Doga", occurred_at=_NOW, kind=ActorKind.HUMAN
    )
    stored = _stored("ActorRegistered", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("SomethingElse", {})
    with pytest.raises(ValueError, match="Unknown ActorEvent event_type"):
        from_stored(stored)


# `to_new_event` envelope construction lives at
# `cora.infrastructure.event_envelope` and is covered by
# `tests/unit/test_event_envelope.py`. Handler-level tests
# (`test_register_actor_handler`, `test_handler_appends_*`) verify
# the envelope shape end-to-end against a real event store.
