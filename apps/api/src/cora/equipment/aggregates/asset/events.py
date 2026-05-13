"""Domain events emitted by the Asset aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes,
discriminated union, `event_type_name`, `to_payload`,
`from_stored`. The persistence-envelope construction (`NewEvent`)
lives at `cora.infrastructure.event_envelope.to_new_event`.

Phase 5b shipped `AssetRegistered`. Phase 5c added `AssetActivated`
and `AssetDecommissioned` (lifecycle transitions). Phase 5d added
`AssetRelocated` — the **first event whose payload carries source
AND target state** (`from_parent_id` + `to_parent_id`), needed
because parent_id is mutable and the audit log should record both
sides of the change without requiring readers to walk the prior
event. Phase 5e added `AssetMaintenanceEntered` and
`AssetRestoredFromMaintenance` (single-source paired transitions:
ACTIVE -> MAINTENANCE and MAINTENANCE -> ACTIVE) and widened the
`AssetDecommissioned` source-state set to also accept MAINTENANCE.
Phase 5f-1 adds `AssetCapabilityAdded` and `AssetCapabilityRemoved`
— first incremental-mutation event pair on Asset state
(capabilities accumulate over the asset's lifetime as new techniques
are commissioned / retired). Each carries a single `capability_id`;
the evolver folds each into the `capabilities` frozenset.

## Payload conventions for Asset

`level` IS carried in the payload (set at registration, never
changes; no `AssetLevelChanged` event in scope). The evolver
reconstructs via `AssetLevel(payload["level"])`.

`parent_id` IS carried in the AssetRegistered payload (sets the
initial value). For mutations, AssetRelocated carries BOTH
`from_parent_id` and `to_parent_id` — the only event in the
codebase to date with source-state in the payload (most
transitions encode the source via the event TYPE; this one needs
explicit source because parent_id is a value with many possible
prior states, not a discrete state-machine state). Serialized as
`str(parent_id)` or `None` (Optional fits naturally into JSON).

`reason` on AssetRelocated is free-text (validated at the API
boundary, not by a domain VO) — operators include why the move
happened (commissioning move, maintenance reorganization,
decommissioning to storage, etc).

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


@dataclass(frozen=True)
class AssetActivated:
    """An asset transitioned into service.

    Lifecycle transition: `Commissioned -> Active`. The evolver
    sets the new lifecycle; no lifecycle field in the payload.
    """

    asset_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetDecommissioned:
    """An asset was retired from service.

    Lifecycle transition: `Commissioned | Active -> Decommissioned`
    (multi-source; widens to include Maintenance in 5e). The
    evolver sets the new lifecycle regardless of which source state
    the asset came from; the decider's source-state guard is what
    enforces the multi-source restriction at command time.
    """

    asset_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetMaintenanceEntered:
    """An asset was taken out of service for maintenance.

    Lifecycle transition: `Active -> Maintenance` (single-source).
    The evolver sets the new lifecycle; no lifecycle field in the
    payload (event TYPE encodes the change). Same convention as
    AssetActivated.
    """

    asset_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetRestoredFromMaintenance:
    """An asset was returned to active service after maintenance.

    Lifecycle transition: `Maintenance -> Active` (single-source).
    The evolver sets the new lifecycle; no lifecycle field in the
    payload (event TYPE encodes the change). The verbose verb-prep-
    noun naming is deliberate: the symmetric `AssetMaintenanceRestored`
    reads ambiguously (sounds like maintenance was restored), so the
    longer form unambiguously captures the asset's direction of
    change.
    """

    asset_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetCapabilityAdded:
    """A Capability was added to an asset's capability set.

    Single-capability event (not bulk-update). Capabilities accumulate
    as operators commission new techniques on the asset; each event
    captures a single addition for clean audit trails ("when did this
    asset gain XRF Mapping?"). The evolver inserts the capability_id
    into `state.capabilities` (frozenset semantics → no-op on
    duplicate at the evolver layer; the decider's strict-not-idempotent
    guard is what enforces "must not already be present" at command
    time).

    Eventual-consistency: `capability_id` is NOT verified against the
    Capability stream. Same precedent as Conduit zone refs (3b),
    Asset parent refs (5b), Method.needs_capabilities (6a).
    """

    asset_id: UUID
    capability_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetCapabilityRemoved:
    """A Capability was removed from an asset's capability set.

    Mirror of `AssetCapabilityAdded`. Single-capability event; the
    evolver removes the capability_id from `state.capabilities`. The
    decider's strict-not-idempotent guard enforces "must currently be
    present" at command time.
    """

    asset_id: UUID
    capability_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetDegraded:
    """An asset's condition transitioned to `Degraded`.

    Condition transition: any condition -> Degraded (target-state
    semantics, mirrors `enter_maintenance`'s lifecycle target). The
    evolver sets the new condition; no condition field in the
    payload (event TYPE encodes the change).

    `reason` is operator-supplied free text (e.g. "hot pixel detected
    at (12, 42)"); validated 1-500 chars at the API boundary, the
    decider trusts the input. Same precedent as `AssetRelocated.reason`.
    """

    asset_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class AssetFaulted:
    """An asset's condition transitioned to `Faulted`.

    Condition transition: any condition -> Faulted. Mirror of
    `AssetDegraded`. Operationally: device is down, requires repair
    before any further use.
    """

    asset_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class AssetRestored:
    """An asset's condition transitioned to `Nominal`.

    Condition transition: any condition -> Nominal. Mirror of
    `AssetDegraded`. Operationally: device fully repaired and back
    to normal operating specs. Partial repairs (Faulted -> Degraded)
    use `degrade_asset`, NOT `restore_asset` with a target arg —
    each slice has a fixed target.
    """

    asset_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class AssetRelocated:
    """An asset's parent in the hierarchy tree changed.

    Hierarchy mutation: `parent_id: from_parent_id -> to_parent_id`.
    Lifecycle is unchanged. Carries BOTH source and target parent
    in the payload — the audit log should record both sides without
    requiring readers to walk the prior event. `reason` is operator-
    supplied free text (e.g. "moved from storage to BL2-IBP", "site
    reorganization 2026-Q3").

    Per BC map: `from_parent_id` is the prior parent, `to_parent_id`
    is the new parent. Both non-null for any non-Enterprise asset
    (Enterprise can't relocate per the decider's hierarchy guard).
    """

    asset_id: UUID
    from_parent_id: UUID
    to_parent_id: UUID
    reason: str
    occurred_at: datetime


# Discriminated union of every event the Asset aggregate emits.
# Add new event classes above and extend this alias when new
# slices land.
AssetEvent = (
    AssetRegistered
    | AssetActivated
    | AssetDecommissioned
    | AssetRelocated
    | AssetMaintenanceEntered
    | AssetRestoredFromMaintenance
    | AssetCapabilityAdded
    | AssetCapabilityRemoved
    | AssetDegraded
    | AssetFaulted
    | AssetRestored
)


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
        case AssetActivated(asset_id=asset_id, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetDecommissioned(asset_id=asset_id, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetRelocated(
            asset_id=asset_id,
            from_parent_id=from_parent_id,
            to_parent_id=to_parent_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "from_parent_id": str(from_parent_id),
                "to_parent_id": str(to_parent_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetMaintenanceEntered(asset_id=asset_id, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetRestoredFromMaintenance(asset_id=asset_id, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetCapabilityAdded(
            asset_id=asset_id,
            capability_id=capability_id,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "capability_id": str(capability_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetCapabilityRemoved(
            asset_id=asset_id,
            capability_id=capability_id,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "capability_id": str(capability_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetDegraded(asset_id=asset_id, reason=reason, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetFaulted(asset_id=asset_id, reason=reason, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetRestored(asset_id=asset_id, reason=reason, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "reason": reason,
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
        case "AssetActivated":
            return AssetActivated(
                asset_id=UUID(payload["asset_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "AssetDecommissioned":
            return AssetDecommissioned(
                asset_id=UUID(payload["asset_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "AssetRelocated":
            return AssetRelocated(
                asset_id=UUID(payload["asset_id"]),
                from_parent_id=UUID(payload["from_parent_id"]),
                to_parent_id=UUID(payload["to_parent_id"]),
                reason=payload["reason"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "AssetMaintenanceEntered":
            return AssetMaintenanceEntered(
                asset_id=UUID(payload["asset_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "AssetRestoredFromMaintenance":
            return AssetRestoredFromMaintenance(
                asset_id=UUID(payload["asset_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "AssetCapabilityAdded":
            return AssetCapabilityAdded(
                asset_id=UUID(payload["asset_id"]),
                capability_id=UUID(payload["capability_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "AssetCapabilityRemoved":
            return AssetCapabilityRemoved(
                asset_id=UUID(payload["asset_id"]),
                capability_id=UUID(payload["capability_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "AssetDegraded":
            return AssetDegraded(
                asset_id=UUID(payload["asset_id"]),
                reason=payload["reason"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "AssetFaulted":
            return AssetFaulted(
                asset_id=UUID(payload["asset_id"]),
                reason=payload["reason"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "AssetRestored":
            return AssetRestored(
                asset_id=UUID(payload["asset_id"]),
                reason=payload["reason"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown AssetEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "AssetActivated",
    "AssetCapabilityAdded",
    "AssetCapabilityRemoved",
    "AssetDecommissioned",
    "AssetDegraded",
    "AssetEvent",
    "AssetFaulted",
    "AssetMaintenanceEntered",
    "AssetRegistered",
    "AssetRelocated",
    "AssetRestored",
    "AssetRestoredFromMaintenance",
    "event_type_name",
    "from_stored",
    "to_payload",
]
