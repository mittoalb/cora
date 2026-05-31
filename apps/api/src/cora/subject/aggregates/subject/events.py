"""Domain events emitted by the Subject aggregate, plus the discriminated union.

Mirrors `cora/access/aggregates/actor/events.py` in shape: event
classes, discriminated union, `event_type_name`, `to_payload`,
`from_stored`. The persistence-envelope construction (`NewEvent`)
lives at `cora.infrastructure.event_envelope.to_new_event`.

Event catalog: `SubjectRegistered` (genesis); the active-phase
transitions (`SubjectMounted`, `SubjectMeasured`, `SubjectRemoved`,
`SubjectDismounted`); and the three terminal disposition events
(`SubjectReturned` / `SubjectStored` / `SubjectDiscarded`), all
transitioning from `Removed`.

The Subject<->Asset binding aligns with LIMS / PROV-O / DDD modern
patterns: `SubjectMounted` carries an optional `reason` field
(additive; legacy stored events fold via `payload.get("reason", "")`)
and `SubjectDismounted(subject_id, from_asset_id, reason, occurred_at)`
captures explicit dismount narrative for the multi-stage
mount/dismount workflow (Mounted | Measured -> Received cycle).

Status is NOT carried in event payloads — the event type itself
encodes the state change (for example, `SubjectMounted -> status=MOUNTED`).
The evolver hardcodes the mapping per match arm. Same precedent as
`ActorDeactivated -> is_active=False`. See state.py docstring for
the rationale.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class SubjectRegistered:
    """A new subject was registered with the facility.

    Status is implicit (`Received`) — the evolver sets it.
    """

    subject_id: UUID
    name: str
    occurred_at: datetime


@dataclass(frozen=True)
class SubjectMounted:
    """A subject was mounted on the apparatus.

    Status transition: `Received -> Mounted`. The evolver sets the
    new status; no status field in the payload.

    `asset_id` records the sample-environment `Equipment.Asset` the
    Subject was mounted on. Captured for "where is sample X?"
    downstream queries and for full sample-handling provenance.
    Eventual-consistency reference: existence verified at handler-
    load time (404 on missing); decider validates Asset lifecycle is
    `Active` at mount time (409 on non-Active).

    `reason`: operator-supplied free text (1-500 chars), captures
    why the mount happened (loaded for run X, calibration, transport
    break completed). Legacy stored events without the field fold
    via `payload.get("reason", "")` (additive-evolution pattern).
    """

    subject_id: UUID
    asset_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class SubjectDismounted:
    """A subject was physically removed from the sample-environment
    apparatus, but is still pre-terminal in its lifecycle.

    Status transition: `Mounted | Measured -> Received`.
    Sample is back to "in the lab, not currently mounted"; can be
    re-mounted via a subsequent `SubjectMounted` event. Distinct from
    `SubjectRemoved` (which is terminal-leading; sample is done with
    the experiment workflow).

    `from_asset_id` records the Asset the Subject was previously
    mounted on. Carried in the payload for self-contained audit
    (mirrors `AssetRelocated` carrying both `from_parent_id` and
    `to_parent_id`); readers don't have to fold prior events to know
    what was dismounted from.

    `reason` is required free text (1-500 chars): why the dismount
    happened (run complete, transport break, transferring to next
    stage, end-of-day storage).
    """

    subject_id: UUID
    from_asset_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class SubjectMeasured:
    """A subject had data collected on it.

    Status transition: `Mounted -> Measured`. Aggregate-level "has
    been measured at least once" — per-measurement detail (which
    scan, params, results) lives in `Run` observation channels later. The
    evolver sets the new status; no status field in the payload.
    """

    subject_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class SubjectRemoved:
    """A subject was removed from the apparatus.

    Status transition: `Mounted | Measured -> Removed` (multi-source).
    The evolver sets the new status regardless of which source state
    the subject came from; the decider's source-state guard is what
    enforces the multi-source restriction at command time.
    """

    subject_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class SubjectReturned:
    """A subject was returned to its owner / submitter.

    Terminal disposition: `Removed -> Returned`. No further
    transitions expected. The evolver sets the new status; no
    status field in the payload.
    """

    subject_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class SubjectStored:
    """A subject was archived on-site.

    Terminal disposition: `Removed -> Stored`. No further transitions
    expected. The evolver sets the new status; no status field in
    the payload.
    """

    subject_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class SubjectDiscarded:
    """A subject was destroyed / discarded.

    Terminal disposition: `Removed -> Discarded`. No further
    transitions expected. The evolver sets the new status; no
    status field in the payload.

    `reason` is a free-form string (1-500 chars after trimming),
    captured verbatim from the operator. Mirrors DatasetDiscarded /
    RunStopped / RunAborted / RunTruncated reason shape; same
    future-additive structured-taxonomy posture. Required for GDPR
    + sample-handling audit: every irrecoverable Subject disposition
    must carry the operator's stated reason.
    """

    subject_id: UUID
    reason: str
    occurred_at: datetime


# Discriminated union of every event the Subject aggregate emits. Add
# new event classes above and extend this alias when new slices land.
SubjectEvent = (
    SubjectRegistered
    | SubjectMounted
    | SubjectMeasured
    | SubjectRemoved
    | SubjectReturned
    | SubjectStored
    | SubjectDiscarded
    | SubjectDismounted
)


def event_type_name(event: SubjectEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: SubjectEvent) -> dict[str, Any]:
    """Serialize a Subject event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601 strings.
    """
    match event:
        case SubjectRegistered(subject_id=subject_id, name=name, occurred_at=occurred_at):
            return {
                "subject_id": str(subject_id),
                "name": name,
                "occurred_at": occurred_at.isoformat(),
            }
        case SubjectMounted(
            subject_id=subject_id,
            asset_id=asset_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "subject_id": str(subject_id),
                "asset_id": str(asset_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case SubjectMeasured(subject_id=subject_id, occurred_at=occurred_at):
            return {
                "subject_id": str(subject_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case SubjectRemoved(subject_id=subject_id, occurred_at=occurred_at):
            return {
                "subject_id": str(subject_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case SubjectReturned(subject_id=subject_id, occurred_at=occurred_at):
            return {
                "subject_id": str(subject_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case SubjectStored(subject_id=subject_id, occurred_at=occurred_at):
            return {
                "subject_id": str(subject_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case SubjectDiscarded(subject_id=subject_id, reason=reason, occurred_at=occurred_at):
            return {
                "subject_id": str(subject_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case SubjectDismounted(
            subject_id=subject_id,
            from_asset_id=from_asset_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "subject_id": str(subject_id),
                "from_asset_id": str(from_asset_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> SubjectEvent:
    """Rebuild a Subject event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "SubjectRegistered":
            return deserialize_or_raise(
                "SubjectRegistered",
                lambda: SubjectRegistered(
                    subject_id=UUID(payload["subject_id"]),
                    name=payload["name"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "SubjectMounted":
            return deserialize_or_raise(
                "SubjectMounted",
                lambda: SubjectMounted(
                    subject_id=UUID(payload["subject_id"]),
                    asset_id=UUID(payload["asset_id"]),
                    reason=payload.get("reason", ""),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "SubjectMeasured":
            return deserialize_or_raise(
                "SubjectMeasured",
                lambda: SubjectMeasured(
                    subject_id=UUID(payload["subject_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "SubjectRemoved":
            return deserialize_or_raise(
                "SubjectRemoved",
                lambda: SubjectRemoved(
                    subject_id=UUID(payload["subject_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "SubjectReturned":
            return deserialize_or_raise(
                "SubjectReturned",
                lambda: SubjectReturned(
                    subject_id=UUID(payload["subject_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "SubjectStored":
            return deserialize_or_raise(
                "SubjectStored",
                lambda: SubjectStored(
                    subject_id=UUID(payload["subject_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "SubjectDiscarded":
            return deserialize_or_raise(
                "SubjectDiscarded",
                lambda: SubjectDiscarded(
                    subject_id=UUID(payload["subject_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "SubjectDismounted":
            return deserialize_or_raise(
                "SubjectDismounted",
                lambda: SubjectDismounted(
                    subject_id=UUID(payload["subject_id"]),
                    from_asset_id=UUID(payload["from_asset_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown SubjectEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "SubjectDiscarded",
    "SubjectDismounted",
    "SubjectEvent",
    "SubjectMeasured",
    "SubjectMounted",
    "SubjectRegistered",
    "SubjectRemoved",
    "SubjectReturned",
    "SubjectStored",
    "event_type_name",
    "from_stored",
    "to_payload",
]
