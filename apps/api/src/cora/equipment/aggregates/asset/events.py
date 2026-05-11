"""Domain events emitted by the Asset aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes,
discriminated union, `event_type_name`, `to_payload`,
`from_stored`. The persistence-envelope construction (`NewEvent`)
lives at `cora.infrastructure.event_envelope.to_new_event`.

Phase 5b ships `AssetRegistered`. Subsequent slices add
`AssetActivated` / `AssetMaintenanceEntered` /
`AssetMaintenanceRestored` / `AssetDecommissioned` (5c, 5e), and
`AssetRelocated` (5d, the first event whose payload carries source
AND target state).

## Payload conventions for Asset

`level` IS carried in the payload (set at registration, never
changes; no `AssetLevelChanged` event in scope). The evolver
reconstructs via `AssetLevel(payload["level"])`.

`parent_id` IS carried in the payload (mutable across
`AssetRelocated` later, but registered once). Serialized as
`str(parent_id)` or `None` (the optional fits naturally into
JSON).

`lifecycle` is NOT carried in the payload — the event TYPE
encodes the state change (`AssetRegistered → COMMISSIONED`).
Same precedent as Subject / Capability / Actor.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class AssetRegistered:
    """A new asset was registered with the facility.

    Lifecycle is implicit (`Commissioned`) — the evolver sets it.
    `parent_id` is optional: only `level=Enterprise` has a null
    parent (the root); other levels enforce non-null at the
    decider per the hierarchy rule.
    """

    asset_id: UUID
    name: str
    level: str  # AssetLevel.value; carried as primitive in the payload
    parent_id: UUID | None
    occurred_at: datetime


# Discriminated union of every event the Asset aggregate emits.
# Add new event classes above and extend this alias when new
# slices land (5c: AssetActivated/Decommissioned; 5d:
# AssetRelocated; 5e: AssetMaintenance*).
AssetEvent = AssetRegistered


def event_type_name(event: AssetEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: AssetEvent) -> dict[str, Any]:
    """Serialize an Asset event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings, optional UUIDs become string-or-None.
    """
    match event:
        case AssetRegistered(
            asset_id=asset_id,
            name=name,
            level=level,
            parent_id=parent_id,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "name": name,
                "level": level,
                "parent_id": str(parent_id) if parent_id is not None else None,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> AssetEvent:
    """Rebuild an Asset event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "AssetRegistered":
            raw_parent = payload["parent_id"]
            return AssetRegistered(
                asset_id=UUID(payload["asset_id"]),
                name=payload["name"],
                level=payload["level"],
                parent_id=UUID(raw_parent) if raw_parent is not None else None,
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown AssetEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "AssetEvent",
    "AssetRegistered",
    "event_type_name",
    "from_stored",
    "to_payload",
]
