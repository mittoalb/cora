"""Domain events emitted by the Surface aggregate.

v1 ships only `SurfaceDefined`. Versioning / deprecation events are
future-additive; the discriminated union is shaped to accept new
members without breaking `event_type_name` / `from_stored` callers.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.trust.aggregates.surface.surface_kind import SurfaceKind


@dataclass(frozen=True)
class SurfaceDefined:
    """A new Surface was defined."""

    surface_id: UUID
    name: str
    kind: SurfaceKind
    occurred_at: datetime


SurfaceEvent = SurfaceDefined


def event_type_name(event: SurfaceEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: SurfaceEvent) -> dict[str, Any]:
    """Serialize a Surface event to a JSON-friendly dict for jsonb storage."""
    match event:
        case SurfaceDefined(
            surface_id=surface_id,
            name=name,
            kind=kind,
            occurred_at=occurred_at,
        ):
            return {
                "surface_id": str(surface_id),
                "name": name,
                "kind": kind.value,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> SurfaceEvent:
    """Rebuild a Surface event from a StoredEvent loaded from the event store."""
    payload = stored.payload
    match stored.event_type:
        case "SurfaceDefined":
            return deserialize_or_raise(
                "SurfaceDefined",
                lambda: SurfaceDefined(
                    surface_id=UUID(payload["surface_id"]),
                    name=payload["name"],
                    kind=SurfaceKind(payload["kind"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
                extra=(ValueError,),
            )
        case _:
            msg = f"Unknown SurfaceEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "SurfaceDefined",
    "SurfaceEvent",
    "event_type_name",
    "from_stored",
    "to_payload",
]
