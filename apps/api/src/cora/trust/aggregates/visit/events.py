"""Domain events emitted by the Visit aggregate, plus the discriminated union.

Nine events ship Phase beta (8 lifecycle transitions + 1 voided terminal):

  - `VisitRegistered`   -- genesis (Planned status)
  - `VisitArrived`      -- Planned -> Arrived
  - `VisitStarted`      -- Arrived -> InProgress
  - `VisitHeld`         -- InProgress -> OnHold (+ reason)
  - `VisitResumed`      -- OnHold -> InProgress
  - `VisitCompleted`    -- InProgress | OnHold -> Completed
  - `VisitCancelled`    -- Planned | Arrived -> Cancelled (+ reason)
  - `VisitAborted`      -- InProgress | OnHold -> Aborted (+ reason)
  - `VisitVoided`       -- any non-terminal -> Voided (+ reason)
                          FHIR `entered-in-error` analog.

Presence events (`VisitCheckedIn` / `VisitCheckedOut`) ship Phase gamma.
Control events (`VisitTookControlOfSurface` / `VisitReleasedControlOfSurface`)
ship Phase delta. Both will land as additive union members.

`VisitRegistered.permitted_*` lists become `frozenset` on state in the
evolver -- same list-on-event / frozenset-on-state pattern as PolicyDefined.
`external_refs` is serialized as a sorted list of dicts in to_payload for
deterministic byte-equality across runs.

`part_of_visit_id` and `external_refs` are on the VisitRegistered event
payload from Phase beta even though their API surface only lands in
Phase delta / Phase epsilon respectively (per design memo P2-Design-3
migration-drift closure). The slice's command exposes them as optional
params with defaults; nothing semantically uses them until later phases
expose them at the API.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.external_ref import ExternalRef
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class VisitRegistered:
    """A new Visit was registered for a Policy + Surface pair."""

    visit_id: UUID
    policy_id: UUID
    surface_id: UUID
    type: str  # VisitType.value -- serialized as string for JSON round-trip
    planned_start_at: datetime
    planned_end_at: datetime
    occurred_at: datetime
    part_of_visit_id: UUID | None = None
    external_refs: frozenset[ExternalRef] = field(default_factory=frozenset[ExternalRef])


@dataclass(frozen=True)
class VisitArrived:
    """The Visit team has arrived (explicit operator gesture).

    Distinct from any presence event (Phase gamma `VisitCheckedIn`).
    Operator may call `arrive_visit` without any individual actor
    check-in (e.g., team here but specific presences not tracked).
    Defends V6 explicit-gesture lock.
    """

    visit_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class VisitStarted:
    """Work on the Visit has begun (explicit operator gesture)."""

    visit_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class VisitHeld:
    """The Visit was paused for an external reason (NOT child commissioning).

    OnHold is reserved for genuine envelope pauses (beam dump, equipment
    fault, safety hold, extended user break). Commissioning-during-user
    does NOT put parent OnHold -- parent stays InProgress; control concern
    lives on `proj_surface_active_visit`.
    """

    visit_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class VisitResumed:
    """The Visit returned to InProgress from OnHold."""

    visit_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class VisitCompleted:
    """The Visit reached normal terminal status."""

    visit_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class VisitCancelled:
    """The Visit was cancelled before work began (Planned or Arrived).

    Distinct from `VisitAborted` (work started then stopped) and from
    `VisitVoided` (registration was a mistake). Cancellation is the
    "real allocation, never started" terminator. HL7 v2 A11 precedent.
    """

    visit_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class VisitAborted:
    """The Visit was stopped mid-work (InProgress or OnHold).

    Distinct from `VisitCancelled` (pre-work) and `VisitVoided` (mistake).
    HL7 v2 A13 precedent.
    """

    visit_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class VisitVoided:
    """The Visit should never have existed (registration was a mistake).

    FHIR R5 `entered-in-error` analog. Distinguished from `VisitCancelled`
    (real allocation, operator pre-work cancel) and `VisitAborted` (real
    work stopped). Reachable from ANY non-terminal status. Use cases:
    BSS double-sent a registration, duplicate Visit, registration error.
    """

    visit_id: UUID
    reason: str
    occurred_at: datetime


# Discriminated union of every event the Visit aggregate emits today.
# Phase gamma / delta add presence + control event arms.
VisitEvent = (
    VisitRegistered
    | VisitArrived
    | VisitStarted
    | VisitHeld
    | VisitResumed
    | VisitCompleted
    | VisitCancelled
    | VisitAborted
    | VisitVoided
)


def event_type_name(event: VisitEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def _external_refs_to_payload(refs: frozenset[ExternalRef]) -> list[dict[str, str]]:
    """Sort + serialize ExternalRefs for deterministic payload bytes."""
    return sorted(
        ({"scheme": r.scheme, "id": r.id} for r in refs),
        key=lambda d: (d["scheme"], d["id"]),
    )


def _external_refs_from_payload(payload: list[dict[str, str]]) -> frozenset[ExternalRef]:
    """Rebuild ExternalRef set from a payload's serialized list."""
    return frozenset(ExternalRef(scheme=item["scheme"], id=item["id"]) for item in payload)


def to_payload(event: VisitEvent) -> dict[str, Any]:
    """Serialize a Visit event to a JSON-friendly dict for jsonb storage."""
    match event:
        case VisitRegistered(
            visit_id=visit_id,
            policy_id=policy_id,
            surface_id=surface_id,
            type=type_,
            planned_start_at=planned_start_at,
            planned_end_at=planned_end_at,
            occurred_at=occurred_at,
            part_of_visit_id=part_of_visit_id,
            external_refs=external_refs,
        ):
            return {
                "visit_id": str(visit_id),
                "policy_id": str(policy_id),
                "surface_id": str(surface_id),
                "type": type_,
                "planned_start_at": planned_start_at.isoformat(),
                "planned_end_at": planned_end_at.isoformat(),
                "occurred_at": occurred_at.isoformat(),
                "part_of_visit_id": (
                    str(part_of_visit_id) if part_of_visit_id is not None else None
                ),
                "external_refs": _external_refs_to_payload(external_refs),
            }
        case VisitArrived(visit_id=visit_id, occurred_at=occurred_at):
            return {
                "visit_id": str(visit_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitStarted(visit_id=visit_id, occurred_at=occurred_at):
            return {
                "visit_id": str(visit_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitHeld(visit_id=visit_id, reason=reason, occurred_at=occurred_at):
            return {
                "visit_id": str(visit_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitResumed(visit_id=visit_id, occurred_at=occurred_at):
            return {
                "visit_id": str(visit_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitCompleted(visit_id=visit_id, occurred_at=occurred_at):
            return {
                "visit_id": str(visit_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitCancelled(visit_id=visit_id, reason=reason, occurred_at=occurred_at):
            return {
                "visit_id": str(visit_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitAborted(visit_id=visit_id, reason=reason, occurred_at=occurred_at):
            return {
                "visit_id": str(visit_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case VisitVoided(visit_id=visit_id, reason=reason, occurred_at=occurred_at):
            return {
                "visit_id": str(visit_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> VisitEvent:
    """Rebuild a Visit event from a StoredEvent loaded from the event store."""
    payload = stored.payload
    match stored.event_type:
        case "VisitRegistered":
            try:
                part_of_raw = payload.get("part_of_visit_id")
                return VisitRegistered(
                    visit_id=UUID(payload["visit_id"]),
                    policy_id=UUID(payload["policy_id"]),
                    surface_id=UUID(payload["surface_id"]),
                    type=payload["type"],
                    planned_start_at=datetime.fromisoformat(payload["planned_start_at"]),
                    planned_end_at=datetime.fromisoformat(payload["planned_end_at"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    part_of_visit_id=UUID(part_of_raw) if part_of_raw is not None else None,
                    external_refs=_external_refs_from_payload(payload.get("external_refs", [])),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed VisitRegistered payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "VisitArrived":
            try:
                return VisitArrived(
                    visit_id=UUID(payload["visit_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed VisitArrived payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "VisitStarted":
            try:
                return VisitStarted(
                    visit_id=UUID(payload["visit_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed VisitStarted payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "VisitHeld":
            try:
                return VisitHeld(
                    visit_id=UUID(payload["visit_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed VisitHeld payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "VisitResumed":
            try:
                return VisitResumed(
                    visit_id=UUID(payload["visit_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed VisitResumed payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "VisitCompleted":
            try:
                return VisitCompleted(
                    visit_id=UUID(payload["visit_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed VisitCompleted payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "VisitCancelled":
            try:
                return VisitCancelled(
                    visit_id=UUID(payload["visit_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed VisitCancelled payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "VisitAborted":
            try:
                return VisitAborted(
                    visit_id=UUID(payload["visit_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed VisitAborted payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "VisitVoided":
            try:
                return VisitVoided(
                    visit_id=UUID(payload["visit_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed VisitVoided payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case _:
            msg = f"Unknown VisitEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "VisitAborted",
    "VisitArrived",
    "VisitCancelled",
    "VisitCompleted",
    "VisitEvent",
    "VisitHeld",
    "VisitRegistered",
    "VisitResumed",
    "VisitStarted",
    "VisitVoided",
    "event_type_name",
    "from_stored",
    "to_payload",
]
