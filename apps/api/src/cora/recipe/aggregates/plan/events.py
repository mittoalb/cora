"""Domain events emitted by the Plan aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

Phase 6e-1 shipped `PlanDefined`. Phase 6e-2 adds `PlanVersioned`
and `PlanDeprecated` per the `Defined → Versioned → Deprecated`
lifecycle, mirroring Method 6b and Practice 6d-2. PlanVersioned
carries an operator-supplied `version_tag`; PlanDeprecated carries
no extra fields.

## Payload conventions

`practice_id` and entries in `asset_ids` carry as primitive UUIDs
(strings in jsonb). Eventual-consistency stance: existence is NOT
verified at the persistence layer — the handler pre-loads them
before reaching the decider (gate-review Q5).

`asset_ids` serializes as a sorted list of UUID-as-strings (the
state holds a `frozenset[UUID]`; sorting by string form keeps the
persisted bytes deterministic — same logical Asset set, same
payload, same idempotency hash). Same precedent as
`Method.needed_capabilities`.

## Audit snapshots in payload (gate-review Q4)

`PlanDefined` carries three audit-only fields that are NOT folded
into Plan state:

  - `method_id`: the Method ultimately implemented by this Plan
    (resolved from `practice.method_id` at handler-load time).
    Captured in the event so audit replay doesn't need to traverse
    Practice → Method (capture-don't-recompute principle).
  - `method_needed_capabilities_snapshot`: the Method's
    `needed_capabilities` AT BIND TIME. Pinned so the audit trail
    reproduces what was checked even if Method later evolves.
  - `asset_capabilities_snapshot`: each bound Asset's `capabilities`
    AT BIND TIME. Same audit pinning rationale.

Both snapshots serialize as primitive forms (sorted UUID lists /
sorted-key dicts of sorted UUID lists) for deterministic hashing.
The evolver does NOT read these snapshots — they're audit-only
data living in the payload, not state.

Status is NOT carried in event payloads — the event type itself
encodes the state change. The evolver hardcodes the mapping per
match arm. Same precedent as PracticeDefined / MethodDefined /
CapabilityDefined / SubjectMounted / ActorDeactivated.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class PlanDefined:
    """A new Plan was defined: Practice + Asset binding established.

    Status is implicit (`Defined`) — the evolver sets it.

    `practice_id` and `asset_ids` are eventual-consistency refs.
    `method_id` and the two snapshots are audit-only data captured
    at bind time (see module docstring).
    """

    plan_id: UUID
    name: str
    practice_id: UUID
    asset_ids: list[UUID]
    method_id: UUID
    method_needed_capabilities_snapshot: list[UUID]
    asset_capabilities_snapshot: dict[UUID, list[UUID]]
    occurred_at: datetime


@dataclass(frozen=True)
class PlanVersioned:
    """A plan's binding was revised; a new version label was issued.

    Multi-source transition: `Defined | Versioned -> Versioned`. The
    evolver sets status=VERSIONED and updates state.version to the
    new tag. The decider's source-state guard enforces that
    Deprecated plans can't be re-versioned.

    `version_tag` is operator-supplied free text (1-50 chars,
    validated at API boundary AND in the decider). Same precedent
    as PracticeVersioned / MethodVersioned / CapabilityVersioned.
    """

    plan_id: UUID
    version_tag: str
    occurred_at: datetime


@dataclass(frozen=True)
class PlanDeprecated:
    """A plan was marked as no longer recommended for new Runs.

    Multi-source transition: `Defined | Versioned -> Deprecated`. The
    evolver sets status=DEPRECATED; `version` is preserved (the
    historical label of when the plan was last revised before
    deprecation remains visible).

    Existing Runs that reference this Plan are NOT automatically
    invalidated. Deprecation is advisory at the BC layer; future
    Run-side enrichment may surface a warning at start-time when
    referencing a deprecated Plan (or Run-start may reject — that's
    a 6f-side decision).
    """

    plan_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class PlanWireAdded:
    """A typed Wire was added to a Plan's wire set (Phase 6h).

    Single-wire event (not bulk-add); mirrors `AssetPortAdded` shape
    from 5h. Audit value: "when did this Plan gain the connection
    from pandabox.trigger_out → camera.trigger_in?"

    The four port-reference fields together form the Wire's
    identity (no separate `wire_id`). Carried as primitives in the
    event payload so `from_stored` can rebuild the `Wire` VO without
    importing state.

    Status is NOT carried — wiring updates are orthogonal to
    lifecycle (Defined / Versioned / Deprecated all permit wiring
    updates; mirrors the 6g-b default-parameters stance and
    PortAdded's lifecycle independence at the Asset side).
    """

    plan_id: UUID
    source_asset_id: UUID
    source_port_name: str
    target_asset_id: UUID
    target_port_name: str
    occurred_at: datetime


@dataclass(frozen=True)
class PlanWireRemoved:
    """A typed Wire was removed from a Plan's wire set (Phase 6h).

    Mirror of `PlanWireAdded`. Carries all 4 endpoint components
    because the Wire's identity IS the 4-tuple (no shorter unique
    key). Symmetric with `AssetPortRemoved` from 5h.
    """

    plan_id: UUID
    source_asset_id: UUID
    source_port_name: str
    target_asset_id: UUID
    target_port_name: str
    occurred_at: datetime


@dataclass(frozen=True)
class PlanDefaultParametersUpdated:
    """The Plan's parameter defaults were updated (Phase 6g-b).

    `default_parameters` is the POST-merge dict (RFC 7396 PATCH
    applied at the slice layer; the event payload carries the
    resolved snapshot, not the patch — same self-contained-audit-log
    precedent as `AssetSettingsUpdated` from 5g-c).

    Validation runs at the decider against the owning Method's
    `parameters_schema` (loaded by the handler before reaching the
    decider, then handed in via the slice's MethodSchemaContext).
    Strict when Method.parameters_schema is None: non-empty defaults
    are rejected.

    Status is NOT carried — defaults updates are orthogonal to
    lifecycle (Defined / Versioned / Deprecated all permit defaults
    updates; mirrors the 6g-a Method-side stance).
    """

    plan_id: UUID
    default_parameters: dict[str, Any]
    occurred_at: datetime


# Discriminated union of every event the Plan aggregate emits.
PlanEvent = (
    PlanDefined
    | PlanVersioned
    | PlanDeprecated
    | PlanDefaultParametersUpdated
    | PlanWireAdded
    | PlanWireRemoved
)


def event_type_name(event: PlanEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def _serialize_asset_capabilities_snapshot(
    snapshot: dict[UUID, list[UUID]],
) -> dict[str, list[str]]:
    """Serialize the bind-time asset-capabilities snapshot deterministically.

    jsonb stores object keys as strings; the dict key sort order
    matters for idempotency-key hashing (same logical snapshot
    must produce identical bytes). Outer keys sorted by UUID string
    form; inner lists sorted by UUID string form.
    """
    return {
        str(asset_id): sorted(str(c) for c in capabilities)
        for asset_id, capabilities in sorted(snapshot.items(), key=lambda kv: str(kv[0]))
    }


def _deserialize_asset_capabilities_snapshot(
    payload: dict[str, list[str]],
) -> dict[UUID, list[UUID]]:
    """Inverse of `_serialize_asset_capabilities_snapshot`."""
    return {UUID(asset_id): [UUID(c) for c in caps] for asset_id, caps in payload.items()}


def to_payload(event: PlanEvent) -> dict[str, Any]:
    """Serialize a Plan event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings, frozensets/dicts become deterministically-ordered lists
    and string-keyed dicts.
    """
    match event:
        case PlanDefined(
            plan_id=plan_id,
            name=name,
            practice_id=practice_id,
            asset_ids=asset_ids,
            method_id=method_id,
            method_needed_capabilities_snapshot=needs_snapshot,
            asset_capabilities_snapshot=asset_caps_snapshot,
            occurred_at=occurred_at,
        ):
            return {
                "plan_id": str(plan_id),
                "name": name,
                "practice_id": str(practice_id),
                # asset_ids deterministic for idempotency hashing.
                "asset_ids": sorted(str(a) for a in asset_ids),
                "method_id": str(method_id),
                "method_needed_capabilities_snapshot": sorted(str(c) for c in needs_snapshot),
                "asset_capabilities_snapshot": _serialize_asset_capabilities_snapshot(
                    asset_caps_snapshot
                ),
                "occurred_at": occurred_at.isoformat(),
            }
        case PlanVersioned(
            plan_id=plan_id,
            version_tag=version_tag,
            occurred_at=occurred_at,
        ):
            return {
                "plan_id": str(plan_id),
                "version_tag": version_tag,
                "occurred_at": occurred_at.isoformat(),
            }
        case PlanDeprecated(plan_id=plan_id, occurred_at=occurred_at):
            return {
                "plan_id": str(plan_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case PlanDefaultParametersUpdated(
            plan_id=plan_id,
            default_parameters=default_parameters,
            occurred_at=occurred_at,
        ):
            return {
                "plan_id": str(plan_id),
                "default_parameters": default_parameters,
                "occurred_at": occurred_at.isoformat(),
            }
        case PlanWireAdded(
            plan_id=plan_id,
            source_asset_id=source_asset_id,
            source_port_name=source_port_name,
            target_asset_id=target_asset_id,
            target_port_name=target_port_name,
            occurred_at=occurred_at,
        ):
            return {
                "plan_id": str(plan_id),
                "source_asset_id": str(source_asset_id),
                "source_port_name": source_port_name,
                "target_asset_id": str(target_asset_id),
                "target_port_name": target_port_name,
                "occurred_at": occurred_at.isoformat(),
            }
        case PlanWireRemoved(
            plan_id=plan_id,
            source_asset_id=source_asset_id,
            source_port_name=source_port_name,
            target_asset_id=target_asset_id,
            target_port_name=target_port_name,
            occurred_at=occurred_at,
        ):
            return {
                "plan_id": str(plan_id),
                "source_asset_id": str(source_asset_id),
                "source_port_name": source_port_name,
                "target_asset_id": str(target_asset_id),
                "target_port_name": target_port_name,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> PlanEvent:
    """Rebuild a Plan event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "PlanDefined":
            return PlanDefined(
                plan_id=UUID(payload["plan_id"]),
                name=payload["name"],
                practice_id=UUID(payload["practice_id"]),
                asset_ids=[UUID(a) for a in payload["asset_ids"]],
                method_id=UUID(payload["method_id"]),
                method_needed_capabilities_snapshot=[
                    UUID(c) for c in payload["method_needed_capabilities_snapshot"]
                ],
                asset_capabilities_snapshot=_deserialize_asset_capabilities_snapshot(
                    payload["asset_capabilities_snapshot"]
                ),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "PlanVersioned":
            return PlanVersioned(
                plan_id=UUID(payload["plan_id"]),
                version_tag=payload["version_tag"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "PlanDeprecated":
            return PlanDeprecated(
                plan_id=UUID(payload["plan_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "PlanDefaultParametersUpdated":
            return PlanDefaultParametersUpdated(
                plan_id=UUID(payload["plan_id"]),
                default_parameters=payload["default_parameters"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "PlanWireAdded":
            return PlanWireAdded(
                plan_id=UUID(payload["plan_id"]),
                source_asset_id=UUID(payload["source_asset_id"]),
                source_port_name=payload["source_port_name"],
                target_asset_id=UUID(payload["target_asset_id"]),
                target_port_name=payload["target_port_name"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "PlanWireRemoved":
            return PlanWireRemoved(
                plan_id=UUID(payload["plan_id"]),
                source_asset_id=UUID(payload["source_asset_id"]),
                source_port_name=payload["source_port_name"],
                target_asset_id=UUID(payload["target_asset_id"]),
                target_port_name=payload["target_port_name"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown PlanEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "PlanDefaultParametersUpdated",
    "PlanDefined",
    "PlanDeprecated",
    "PlanEvent",
    "PlanVersioned",
    "PlanWireAdded",
    "PlanWireRemoved",
    "event_type_name",
    "from_stored",
    "to_payload",
]
