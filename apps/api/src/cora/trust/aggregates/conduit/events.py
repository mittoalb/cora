"""Domain events emitted by the Conduit aggregate, plus the discriminated union.

Mirrors `cora/trust/aggregates/zone/events.py` in shape: event
classes, discriminated union, `event_type_name`, `to_payload`,
`from_stored`. The persistence-envelope construction (`NewEvent`)
lives at `cora.infrastructure.event_envelope.to_new_event`.

Phase 3b shipped `ConduitDefined`. Phase 6f-5a adds:
  - `ConduitChannelOpened` — declares a new observation channel
    attached to the Conduit. Carries the channel id, kind
    discriminator (e.g., `"traversals"`), and the schema declaration
    documenting what columns the observation rows will have. Today
    the only channel kind is `traversals` (per-decision authz audit
    log), opened automatically at conduit-creation.
  - `ConduitChannelClosed` — terminates a channel. Future-additive;
    no current path emits it (the traversals channel never closes
    until conduit-archive ships, which is itself deferred).

Channel events DO live on the Conduit's main event stream — they
are part of the Conduit's lifecycle audit (compliance grade: an
auditor can replay the Conduit stream alone and see when each
channel was opened, with what schema, and when it closed). The
high-cardinality observation rows themselves live in separate
`observations_<kind>` tables and do NOT fold into Conduit state.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.channel import ChannelSchema
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class ConduitDefined:
    """A new Trust conduit was defined between two zones."""

    conduit_id: UUID
    name: str
    source_zone_id: UUID
    target_zone_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class ConduitChannelOpened:
    """An observation channel was attached to this Conduit.

    `channel_id` is a fresh UUIDv7 from the IdGenerator; uniquely
    identifies this channel session and tags every observation row
    written to it. `kind` is the discriminator (today: `traversals`).
    `schema` declares the per-observation column shape — carried in
    the event payload so the lifecycle audit captures the schema as
    of this opening (G8 lock; supports per-channel schema evolution
    by declaring a new `kind` or a new channel with updated schema).
    """

    conduit_id: UUID
    channel_id: UUID
    kind: str
    schema: ChannelSchema
    occurred_at: datetime


@dataclass(frozen=True)
class ConduitChannelClosed:
    """An observation channel attached to this Conduit was closed.

    Future-additive (no command path emits this today). When
    conduit-archive ships, it will auto-close every open channel
    before the archive transition (mirrors the Run terminal
    auto-close pattern from 6f-3 L3).
    """

    conduit_id: UUID
    channel_id: UUID
    occurred_at: datetime


# Discriminated union of every event the Conduit aggregate emits.
ConduitEvent = ConduitDefined | ConduitChannelOpened | ConduitChannelClosed


def event_type_name(event: ConduitEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: ConduitEvent) -> dict[str, Any]:
    """Serialize a Conduit event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601 strings.
    `ChannelSchema` serializes via its own `to_dict()`.
    """
    match event:
        case ConduitDefined(
            conduit_id=conduit_id,
            name=name,
            source_zone_id=source_zone_id,
            target_zone_id=target_zone_id,
            occurred_at=occurred_at,
        ):
            return {
                "conduit_id": str(conduit_id),
                "name": name,
                "source_zone_id": str(source_zone_id),
                "target_zone_id": str(target_zone_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case ConduitChannelOpened(
            conduit_id=conduit_id,
            channel_id=channel_id,
            kind=kind,
            schema=schema,
            occurred_at=occurred_at,
        ):
            return {
                "conduit_id": str(conduit_id),
                "channel_id": str(channel_id),
                "kind": kind,
                "schema": schema.to_dict(),
                "occurred_at": occurred_at.isoformat(),
            }
        case ConduitChannelClosed(
            conduit_id=conduit_id,
            channel_id=channel_id,
            occurred_at=occurred_at,
        ):
            return {
                "conduit_id": str(conduit_id),
                "channel_id": str(channel_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> ConduitEvent:
    """Rebuild a Conduit event from a StoredEvent loaded from the event store."""
    payload = stored.payload
    match stored.event_type:
        case "ConduitDefined":
            return ConduitDefined(
                conduit_id=UUID(payload["conduit_id"]),
                name=payload["name"],
                source_zone_id=UUID(payload["source_zone_id"]),
                target_zone_id=UUID(payload["target_zone_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "ConduitChannelOpened":
            return ConduitChannelOpened(
                conduit_id=UUID(payload["conduit_id"]),
                channel_id=UUID(payload["channel_id"]),
                kind=payload["kind"],
                schema=ChannelSchema.from_dict(payload["schema"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "ConduitChannelClosed":
            return ConduitChannelClosed(
                conduit_id=UUID(payload["conduit_id"]),
                channel_id=UUID(payload["channel_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown ConduitEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "ConduitChannelClosed",
    "ConduitChannelOpened",
    "ConduitDefined",
    "ConduitEvent",
    "event_type_name",
    "from_stored",
    "to_payload",
]
