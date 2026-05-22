"""Domain events emitted by the Actor aggregate, plus the discriminated union.

Events live in the aggregate folder (not the slice) because they are
intrinsic facts about the aggregate's history -- the slice just decides
when to emit them. The evolver dispatches on the union; new event types
are appended both as a class definition and to the union alias.

Per the locked "primitives in events" convention, payloads serialize
to plain dicts of primitives. `to_payload` and `from_stored` are the
single home for the (de)serialization logic; per-slice handlers no
longer carry their own serializers.

The persistence envelope (`NewEvent` construction) lives at
`cora.infrastructure.event_envelope.to_new_event` -- handlers call it
directly with `event_type=event_type_name(event)` and
`payload=to_payload(event)` arguments. This module owns only the
genuinely aggregate-specific pieces.

## Additive evolution: `kind` on `ActorRegistered`

`ActorRegistered.kind` discriminates `human` from `agent` Actors.
Per [[project_agent_bc_design]], every Agent in the Agent BC has a
corresponding Actor in Access BC sharing the same `id`, written
atomically via `EventStore.append_streams` from `define_agent`.
Pre-8f-a `ActorRegistered` events lack the `kind` field;
`from_stored` falls back to `"human"` via `payload.get("kind",
"human")` for forward-compat replay (no upcaster needed).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.access.aggregates.actor.state import ActorKind
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class ActorRegistered:
    """A new actor was registered.

    `kind` discriminates `human` vs `agent` (additive evolution).
    REQUIRED at construction: both callsites
    (`register_actor` in Access BC, `define_agent` in Agent BC)
    MUST pass it explicitly so drift between them surfaces as a
    pyright error rather than silently minting an agent-kind Actor
    through the human path. See [[project_agent_bc_design]] P0-4
    cleanup pass.

    Forward-compat replay of pre-8f-a `ActorRegistered` payloads
    (which lack the `kind` field) is handled in `from_stored` via
    `payload.get("kind", "human")`. The dataclass has no default;
    the payload deserializer supplies it.
    """

    actor_id: UUID
    name: str
    occurred_at: datetime
    kind: ActorKind


@dataclass(frozen=True)
class ActorDeactivated:
    """An existing actor was deactivated. The actor remains in the
    system but `Actor.is_active` flips to False."""

    actor_id: UUID
    occurred_at: datetime


# Discriminated union of every event the Actor aggregate emits. Add new
# event classes above and extend this alias when new slices land.
ActorEvent = ActorRegistered | ActorDeactivated


def event_type_name(event: ActorEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: ActorEvent) -> dict[str, Any]:
    """Serialize an Actor event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601 strings.
    The evolver re-validates by reconstructing value objects on the read
    path; this round-trip is the safety net for schema evolution.
    """
    match event:
        case ActorRegistered(actor_id=actor_id, name=name, occurred_at=occurred_at, kind=kind):
            return {
                "actor_id": str(actor_id),
                "name": name,
                "occurred_at": occurred_at.isoformat(),
                "kind": kind.value,
            }
        case ActorDeactivated(actor_id=actor_id, occurred_at=occurred_at):
            return {
                "actor_id": str(actor_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> ActorEvent:
    """Rebuild an Actor event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.

    `kind` field on `ActorRegistered` is forward-compat: pre-8f-a
    events lack it, so `payload.get("kind", "human")` supplies the
    default.
    """
    payload = stored.payload
    match stored.event_type:
        case "ActorRegistered":
            try:
                return ActorRegistered(
                    actor_id=UUID(payload["actor_id"]),
                    name=payload["name"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    kind=ActorKind(payload.get("kind", ActorKind.HUMAN.value)),
                )
            except (KeyError, TypeError, AttributeError, ValueError) as exc:
                msg = f"Malformed ActorRegistered payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "ActorDeactivated":
            try:
                return ActorDeactivated(
                    actor_id=UUID(payload["actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError, ValueError) as exc:
                msg = f"Malformed ActorDeactivated payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case _:
            msg = f"Unknown ActorEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "ActorDeactivated",
    "ActorEvent",
    "ActorRegistered",
    "event_type_name",
    "from_stored",
    "to_payload",
]
