"""Unit tests for the Actor aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

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
def test_event_type_name_returns_v2_discriminator_for_actor_registered() -> None:
    """Per the PII vault Marten/Axon legacy-rename pattern, new
    writes use the V2 discriminator string. The legacy
    "ActorRegistered" string only appears in `from_stored`."""
    actor_id = uuid4()
    event = ActorRegistered(actor_id=actor_id, occurred_at=_NOW, kind=ActorKind.HUMAN)
    assert event_type_name(event) == "ActorRegisteredV2"


@pytest.mark.unit
def test_to_payload_serializes_actor_registered_without_pii() -> None:
    """V2 payload carries no `name` — display name lives in actor_profile."""
    actor_id = uuid4()
    event = ActorRegistered(actor_id=actor_id, occurred_at=_NOW, kind=ActorKind.HUMAN)
    assert to_payload(event) == {
        "actor_id": str(actor_id),
        "occurred_at": _NOW.isoformat(),
        "kind": "human",
    }


@pytest.mark.unit
def test_to_payload_serializes_agent_kind() -> None:
    """ActorRegistered with kind=agent serializes correctly (still no PII)."""
    actor_id = uuid4()
    event = ActorRegistered(actor_id=actor_id, occurred_at=_NOW, kind=ActorKind.AGENT)
    assert to_payload(event) == {
        "actor_id": str(actor_id),
        "occurred_at": _NOW.isoformat(),
        "kind": "agent",
    }


@pytest.mark.unit
def test_from_stored_rebuilds_v2_actor_registered() -> None:
    """A V2 payload (no name) round-trips correctly via the
    "ActorRegisteredV2" event_type discriminator."""
    actor_id = uuid4()
    stored = _stored(
        "ActorRegisteredV2",
        {
            "actor_id": str(actor_id),
            "occurred_at": _NOW.isoformat(),
            "kind": "human",
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == ActorRegistered(actor_id=actor_id, occurred_at=_NOW, kind=ActorKind.HUMAN)


@pytest.mark.unit
def test_from_stored_legacy_v1_drops_name_field_on_rebuild() -> None:
    """V1 (pre-PII-vault) payloads carry `name`; the legacy arm
    drops it on rebuild. The backfill migration copied legacy
    names into actor_profile before this arm started replaying,
    so display reads still find the right name via load_actor_display_name."""
    actor_id = uuid4()
    stored = _stored(
        "ActorRegistered",
        {
            "actor_id": str(actor_id),
            "name": "Doga (legacy V1)",
            "occurred_at": _NOW.isoformat(),
            "kind": "human",
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == ActorRegistered(actor_id=actor_id, occurred_at=_NOW, kind=ActorKind.HUMAN)


@pytest.mark.unit
def test_from_stored_legacy_v1_payload_without_kind_folds_to_human() -> None:
    """Pre-8f-a V1 payloads lack both `kind` and the post-vault
    discriminator — the legacy arm still rebuilds them, defaulting
    kind to human."""
    actor_id = uuid4()
    stored = _stored(
        "ActorRegistered",
        {
            "actor_id": str(actor_id),
            "name": "Doga (pre-kind V1)",
            "occurred_at": _NOW.isoformat(),
            # No "kind" field; oldest legacy shape.
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == ActorRegistered(actor_id=actor_id, occurred_at=_NOW, kind=ActorKind.HUMAN)


@pytest.mark.unit
def test_from_stored_rebuilds_agent_kind_actor() -> None:
    """An agent-kind Actor V2 payload replays correctly."""
    actor_id = uuid4()
    stored = _stored(
        "ActorRegisteredV2",
        {
            "actor_id": str(actor_id),
            "occurred_at": _NOW.isoformat(),
            "kind": "agent",
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == ActorRegistered(actor_id=actor_id, occurred_at=_NOW, kind=ActorKind.AGENT)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_v2() -> None:
    """Round-trip safety net: V2 (de)serialization pair must be each other's inverse."""
    actor_id = uuid4()
    original = ActorRegistered(actor_id=actor_id, occurred_at=_NOW, kind=ActorKind.HUMAN)
    stored = _stored(event_type_name(original), to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("SomethingElse", {})
    with pytest.raises(ValueError, match="Unknown ActorEvent event_type"):
        from_stored(stored)


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    ["ActorRegisteredV2", "ActorRegistered", "ActorDeactivated"],
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


# `to_new_event` envelope construction lives at
# `cora.infrastructure.event_envelope` and is covered by
# `tests/unit/test_event_envelope.py`. Handler-level tests
# (`test_register_actor_handler`, `test_handler_appends_*`) verify
# the envelope shape end-to-end against a real event store.


# ---------- service_account kind + invalid-kind wrap ----------


@pytest.mark.unit
def test_from_stored_rebuilds_service_account_kind_actor_v2() -> None:
    """ActorKind includes SERVICE_ACCOUNT. Pin the
    V2 serialize → from_stored round-trip end-to-end."""
    actor_id = UUID("01900000-0000-7000-8000-000000000099")
    event = ActorRegistered(
        actor_id=actor_id,
        occurred_at=_NOW,
        kind=ActorKind.SERVICE_ACCOUNT,
    )
    stored = _stored(event_type_name(event), to_payload(event))
    rebuilt = from_stored(stored)
    assert rebuilt == event


@pytest.mark.unit
def test_from_stored_wraps_invalid_kind_value() -> None:
    """Gate-review test#11 (pre-existing convention bug surfaced by
    the SERVICE_ACCOUNT enum widening): a corrupted V2 payload with
    kind='superuser' triggers ActorKind() to raise bare ValueError,
    which the previous except clause did NOT catch, leaking a raw
    uncaught ValueError out of from_stored instead of the tagged
    Malformed* shape. The fix adds ValueError to the wrap tuple."""
    actor_id = UUID("01900000-0000-7000-8000-0000000000ab")
    payload: dict[str, object] = {
        "actor_id": str(actor_id),
        "occurred_at": _NOW.isoformat(),
        "kind": "superuser",  # not in ActorKind
    }
    stored = _stored("ActorRegisteredV2", payload)
    with pytest.raises(ValueError, match="Malformed ActorRegisteredV2 payload"):
        from_stored(stored)
