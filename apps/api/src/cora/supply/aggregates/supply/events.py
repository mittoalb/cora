"""Domain events emitted by the Supply aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

Phase 10a-a ships `SupplyRegistered` (genesis -> Unknown) and
`SupplyMarkedAvailable` (Unknown -> Available, operator-asserted
first observation). Phase 10a-b adds `SupplyDegraded`,
`SupplyMarkedUnavailable`, `SupplyMarkedRecovering`, and
`SupplyRestored` for the full degradation/recovery cycle.

Status is NOT carried in `SupplyRegistered` / `SupplyMarkedAvailable`
payloads — the event type IS the state-change indicator (matches
`CapabilityDefined -> DEFINED`, `SubjectMounted -> MOUNTED`). Status
DOES travel in transition-event payloads as `from_status` (10a-b
transitions) so the projection can reconstruct exact source-state
audit without re-folding the prior stream.

`scope` and `kind` travel in the genesis payload as primitive strings;
the evolver reconstructs typed `SupplyScope` and `SupplyKind` VOs.
Same precedent as `AssetLevel` in payloads.

`trigger` travels in transition-event payloads as a `TriggerSource`
enum string. Locked 3-value day one (`Operator | Monitor | Auto`)
even though only `Operator` is wired in 10a-a/b. Forward-compat
motivation in [[project_supply_design]].

`reason` travels in transition-event payloads as a primitive string
(validated and trimmed via `SupplyReason` VO at the decider; payload
carries the trimmed value). Same precedent as `AssetRelocated.reason`
+ `RunAborted.reason`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class SupplyRegistered:
    """A new continuously-available resource was registered.

    Status is implicit (`Unknown`) — the evolver sets it. Per the
    universal initial-state convention (Tango UNKNOWN, EPICS UDF,
    Azure Resource Health Unknown, k8s Pending), a newly-registered
    Supply has not yet been observed and therefore has no asserted
    availability state.
    """

    supply_id: UUID
    scope: str
    kind: str
    name: str
    occurred_at: datetime


@dataclass(frozen=True)
class SupplyMarkedAvailable:
    """An operator declared the Supply Available for the first time.

    Single-source transition: `Unknown -> Available`. Distinct from
    `SupplyRestored` (`Recovering -> Available`, recovery
    acknowledgement) per the Phoebus latched-alarm precedent: first-
    observation declaration and recovery-confirmation are two
    different operator gestures even though they target the same
    `Available` status.

    `from_status` is always `Unknown` in 10a-a; carried in the
    payload anyway for projection-update simplicity and audit
    clarity (matches the 10a-b transition events' shape).

    `reason` is a free-form short string explaining the operator's
    declaration ("operator confirms LN2 supply is up after morning
    walkdown"). Validated 1-500 chars in the decider via
    `SupplyReason` VO.

    `trigger` is the locked 3-value `TriggerSource` enum, always
    `Operator` in 10a-a (substream-driven `Monitor` and timer-driven
    `Auto` are deferred-with-trigger).
    """

    supply_id: UUID
    from_status: str
    reason: str
    trigger: str
    occurred_at: datetime


# Discriminated union of every event the Supply aggregate emits in 10a-a.
# Phase 10a-b widens to: SupplyEvent = (
#     SupplyRegistered | SupplyMarkedAvailable | SupplyDegraded
#     | SupplyMarkedUnavailable | SupplyMarkedRecovering | SupplyRestored
# )
SupplyEvent = SupplyRegistered | SupplyMarkedAvailable


def event_type_name(event: SupplyEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: SupplyEvent) -> dict[str, Any]:
    """Serialize a Supply event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings. Enum values travel as their string values (already
    str-typed via StrEnum but cast here for explicitness).
    """
    match event:
        case SupplyRegistered(
            supply_id=supply_id,
            scope=scope,
            kind=kind,
            name=name,
            occurred_at=occurred_at,
        ):
            return {
                "supply_id": str(supply_id),
                "scope": scope,
                "kind": kind,
                "name": name,
                "occurred_at": occurred_at.isoformat(),
            }
        case SupplyMarkedAvailable(
            supply_id=supply_id,
            from_status=from_status,
            reason=reason,
            trigger=trigger,
            occurred_at=occurred_at,
        ):
            return {
                "supply_id": str(supply_id),
                "from_status": from_status,
                "reason": reason,
                "trigger": trigger,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> SupplyEvent:
    """Rebuild a Supply event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "SupplyRegistered":
            return SupplyRegistered(
                supply_id=UUID(payload["supply_id"]),
                scope=payload["scope"],
                kind=payload["kind"],
                name=payload["name"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "SupplyMarkedAvailable":
            return SupplyMarkedAvailable(
                supply_id=UUID(payload["supply_id"]),
                from_status=payload["from_status"],
                reason=payload["reason"],
                trigger=payload["trigger"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown SupplyEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "SupplyEvent",
    "SupplyMarkedAvailable",
    "SupplyRegistered",
    "event_type_name",
    "from_stored",
    "to_payload",
]
