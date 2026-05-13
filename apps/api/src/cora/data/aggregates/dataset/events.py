"""Domain events emitted by the Dataset aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

## Phase 7a/7b scope

  - `DatasetRegistered` (7a, genesis): identity, URI, checksum
    (algorithm + value), byte_size, encoding (media_type + sorted
    conforms_to list), producing_run_id, subject_id, derived_from
    (sorted UUID list), occurred_at.
  - `DatasetDiscarded` (7b, terminal): dataset_id, free-form
    `reason: str` (1-500 chars after trimming), occurred_at. Mirrors
    RunStopped / RunAborted / RunTruncated reason shape.

## Payload conventions

- UUIDs serialize as strings; UUID-set fields (`derived_from`)
  serialize as sorted string lists (matches the Policy precedent
  for set-semantic fields, so two registrations of the same logical
  Dataset produce byte-identical jsonb).
- `conforms_to` (in encoding) serializes as a sorted string list
  for the same reason.
- Optional refs (`producing_run_id`, `subject_id`) serialize as
  null when None.
- `encoding` serializes as a nested object: `{"media_type": str,
  "conforms_to": list[str]}`.
- `checksum` serializes as a nested object: `{"algorithm": str,
  "value": str}`.
- Status is NOT carried in the payload; the event type encodes it
  (DatasetRegistered → REGISTERED), same precedent as the rest of
  the codebase.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class DatasetRegistered:
    """A new Dataset was registered with the facility.

    Status is implicit (`Registered`); the evolver sets it. All
    cross-aggregate refs (`producing_run_id`, `subject_id`,
    `derived_from`) are eventual-consistency primitives.

    Per CONTRIBUTING.md "Primitives in event payloads": every field
    here is a primitive (str, int, UUID, datetime, frozenset of
    primitives). VOs (`DatasetChecksum`, `DatasetEncoding`) are
    reconstructed by the evolver on fold; the decider unwraps VOs
    before constructing the event.
    """

    dataset_id: UUID
    name: str
    uri: str
    checksum_algorithm: str
    checksum_value: str
    byte_size: int
    media_type: str
    conforms_to: frozenset[str]
    producing_run_id: UUID | None
    subject_id: UUID | None
    derived_from: frozenset[UUID]
    occurred_at: datetime


@dataclass(frozen=True)
class DatasetDiscarded:
    """A Dataset was discarded (Registered → Discarded terminal).

    `reason` is a free-form string (1-500 chars after trimming),
    captured verbatim from the operator. Mirrors RunStopped /
    RunAborted / RunTruncated reason shape; same future-additive
    structured-taxonomy posture.

    GDPR-shaped: bytes at the URI are gone but this event keeps the
    metadata + reason for audit. The Discarded record itself does
    NOT capture the URI's deletion-time-state (operators may need
    to re-discover the original URI to re-run analysis chains); the
    URI lives on the prior DatasetRegistered event.
    """

    dataset_id: UUID
    reason: str
    occurred_at: datetime


# Discriminated union of every event the Dataset aggregate emits.
DatasetEvent = DatasetRegistered | DatasetDiscarded


def event_type_name(event: DatasetEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: DatasetEvent) -> dict[str, Any]:
    """Serialize a Dataset event to a JSON-friendly dict for jsonb storage.

    Set-semantic fields (`derived_from`, `encoding.conforms_to`)
    sort deterministically so two registrations of the same logical
    Dataset produce byte-identical jsonb.
    """
    match event:
        case DatasetRegistered(
            dataset_id=dataset_id,
            name=name,
            uri=uri,
            checksum_algorithm=checksum_algorithm,
            checksum_value=checksum_value,
            byte_size=byte_size,
            media_type=media_type,
            conforms_to=conforms_to,
            producing_run_id=producing_run_id,
            subject_id=subject_id,
            derived_from=derived_from,
            occurred_at=occurred_at,
        ):
            return {
                "dataset_id": str(dataset_id),
                "name": name,
                "uri": uri,
                "checksum": {
                    "algorithm": checksum_algorithm,
                    "value": checksum_value,
                },
                "byte_size": byte_size,
                "encoding": {
                    "media_type": media_type,
                    "conforms_to": sorted(conforms_to),
                },
                "producing_run_id": (
                    str(producing_run_id) if producing_run_id is not None else None
                ),
                "subject_id": str(subject_id) if subject_id is not None else None,
                "derived_from": sorted(str(d) for d in derived_from),
                "occurred_at": occurred_at.isoformat(),
            }
        case DatasetDiscarded(dataset_id=dataset_id, reason=reason, occurred_at=occurred_at):
            return {
                "dataset_id": str(dataset_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> DatasetEvent:
    """Rebuild a Dataset event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "DatasetRegistered":
            raw_producing_run_id = payload["producing_run_id"]
            raw_subject_id = payload["subject_id"]
            raw_checksum = payload["checksum"]
            raw_encoding = payload["encoding"]
            return DatasetRegistered(
                dataset_id=UUID(payload["dataset_id"]),
                name=payload["name"],
                uri=payload["uri"],
                checksum_algorithm=raw_checksum["algorithm"],
                checksum_value=raw_checksum["value"],
                byte_size=int(payload["byte_size"]),
                media_type=raw_encoding["media_type"],
                conforms_to=frozenset(raw_encoding["conforms_to"]),
                producing_run_id=(
                    UUID(raw_producing_run_id) if raw_producing_run_id is not None else None
                ),
                subject_id=UUID(raw_subject_id) if raw_subject_id is not None else None,
                derived_from=frozenset(UUID(d) for d in payload["derived_from"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "DatasetDiscarded":
            return DatasetDiscarded(
                dataset_id=UUID(payload["dataset_id"]),
                reason=payload["reason"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown DatasetEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "DatasetDiscarded",
    "DatasetEvent",
    "DatasetRegistered",
    "event_type_name",
    "from_stored",
    "to_payload",
]
