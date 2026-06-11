"""Domain events emitted by the Edition aggregate plus the discriminated union.

Six events across the 5 slices A-E:

  - EditionRegistered (genesis, -> Registered)
  - EditionDatasetAdded (Registered-state mutation)
  - EditionDatasetRemoved (Registered-state mutation)
  - EditionSealed (Registered -> Sealed)
  - EditionPublished (Sealed -> Published)
  - EditionWithdrawn (Published -> Withdrawn)

All event class names are noun-LAST (`Edition<Subject><Verb-Past-Participle>`)
per the locked R3 naming convention; aggregate-scope prefix first,
past-participle verb last.

## Payload conventions

  - UUIDs serialize as strings; UUID-set fields (`dataset_ids`,
    `sealed_dataset_ids`) serialize as sorted string lists for
    byte-identical jsonb on re-emit (set-semantic-sorted convention).
  - `creators` serializes as an ordered list of
    `{"actor_id": str, "affiliation": str | None}` objects; order is
    publication-significant (first-author convention), NEVER sorted.
  - `kind`, `publisher_facility_code`, `license`,
    `external_pid_scheme`, `withdrawal_reason` serialize as bare
    strings per the wire-payload bare-str convention; typed VO
    wrappers reconstruct at fold time.
  - Optional refs serialize as null when None.
  - Status is NOT carried in any payload; the event type IS the
    status discriminator.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId


@dataclass(frozen=True)
class EditionRegistered:
    """A new Edition was registered with the given kind, title, creators, datasets.

    Status is implicit (`Registered`); the evolver sets it. Genesis
    fields are immutable thereafter on the aggregate.

    `dataset_ids` carries the initial members as a sorted tuple of
    UUIDs (sorted by the decider for byte-identical jsonb on re-emit).

    `creators` carries the ordered tuple of `{"actor_id", "affiliation"}`
    dicts (order publication-significant; NEVER sorted on wire).

    `publisher_facility_code`, `license`, and `publication_year` are
    operator-supplied at register-time when known; otherwise nullable
    and supplied at seal-time. Validation of those values happens at
    register-decider for whatever was supplied; the seal-decider
    re-validates the final composite at the Sealed transition.
    """

    edition_id: UUID
    kind: str
    title: str
    dataset_ids: tuple[UUID, ...]
    creators: tuple[dict[str, Any], ...]
    publisher_facility_code: str | None
    publication_year: int | None
    license: str | None
    occurred_at: datetime
    registered_by: ActorId


@dataclass(frozen=True)
class EditionDatasetAdded:
    """A Dataset was added to a Registered Edition.

    Single-dataset event grain per AssetPortAdded / PlanWireAdded
    precedent. Strict-not-idempotent: re-add raises
    `EditionDatasetAlreadyMemberError` at the decider.
    """

    edition_id: UUID
    dataset_id: UUID
    occurred_at: datetime
    added_by: ActorId


@dataclass(frozen=True)
class EditionDatasetRemoved:
    """A Dataset was removed from a Registered Edition.

    Mirror of `EditionDatasetAdded`. Strict-not-idempotent: not-member
    raises `EditionDatasetNotMemberError` at the decider. No `reason`
    field today (pre-Sealed membership churn is exploratory
    editing).
    """

    edition_id: UUID
    dataset_id: UUID
    occurred_at: datetime
    removed_by: ActorId


@dataclass(frozen=True)
class EditionSealed:
    """A Registered Edition transitioned to Sealed.

    `sealed_dataset_ids` lives on the event payload as the immutability
    anchor (sorted tuple). Aggregate state keeps the mutable
    `dataset_ids: frozenset[UUID]`; the payload captures the snapshot.

    `content_hash` is the sha256 of the pre-DOI serializer output;
    immutable on the aggregate state thereafter.

    `publisher_facility_code` is non-None at Sealed (FacilityLookup-
    resolved at the handler); `publication_year` non-None at Sealed
    (auto-set from sealing-clock UTC year or override). `license`
    remains nullable per the kind-gate (required for DataCite /
    Croissant, optional otherwise).
    """

    edition_id: UUID
    content_hash: str
    publisher_facility_code: str
    publication_year: int
    license: str | None
    sealed_dataset_ids: tuple[UUID, ...]
    occurred_at: datetime
    sealed_by: ActorId


@dataclass(frozen=True)
class EditionPublished:
    """A Sealed Edition transitioned to Published; DOI minted at the authority.

    Scheme + value split per `AssetPersistentIdAssigned` precedent.
    `published_content_hash` is the sha256 of the re-serialized
    post-DOI bytes (distinct from the aggregate's `content_hash`).
    Set-once at aggregate level: stream contains AT MOST ONE
    EditionPublished per Edition.
    """

    edition_id: UUID
    external_pid_scheme: str
    external_pid_value: str
    published_content_hash: str
    occurred_at: datetime
    published_by: ActorId


@dataclass(frozen=True)
class EditionWithdrawn:
    """A Published Edition was tombstoned; DOI stays Findable as a tombstone.

    `withdrawal_reason` is mandatory (unlike `EditionDatasetRemoved`):
    tombstoning a public DOI MUST carry WHY forever.
    """

    edition_id: UUID
    withdrawal_reason: str
    occurred_at: datetime
    withdrawn_by: ActorId


#: Discriminated union over Edition events.
EditionEvent = (
    EditionRegistered
    | EditionDatasetAdded
    | EditionDatasetRemoved
    | EditionSealed
    | EditionPublished
    | EditionWithdrawn
)


def event_type_name(event: EditionEvent) -> str:
    """Discriminator string written into ``StoredEvent.event_type``."""
    return type(event).__name__


def _creators_to_payload(
    creators: tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    """Render the creators tuple to a JSON-friendly list.

    Order is preserved (first-author convention; NEVER sorted).
    Each entry is `{"actor_id": str, "affiliation": str | None}`.
    """
    out: list[dict[str, Any]] = []
    for entry in creators:
        actor_id = entry["actor_id"]
        affiliation = entry.get("affiliation")
        out.append(
            {
                "actor_id": str(actor_id),
                "affiliation": affiliation,
            }
        )
    return out


def _creators_from_payload(
    raw: list[dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Rebuild the creators tuple from a stored payload entry list."""
    out: list[dict[str, Any]] = []
    for entry in raw:
        out.append(
            {
                "actor_id": ActorId(UUID(entry["actor_id"])),
                "affiliation": entry.get("affiliation"),
            }
        )
    return tuple(out)


def to_payload(event: EditionEvent) -> dict[str, Any]:
    """Serialize an Edition event to a JSON-friendly dict for jsonb storage."""
    match event:
        case EditionRegistered(
            edition_id=edition_id,
            kind=kind,
            title=title,
            dataset_ids=dataset_ids,
            creators=creators,
            publisher_facility_code=publisher_facility_code,
            publication_year=publication_year,
            license=license_value,
            occurred_at=occurred_at,
            registered_by=registered_by,
        ):
            return {
                "edition_id": str(edition_id),
                "kind": kind,
                "title": title,
                "dataset_ids": sorted(str(d) for d in dataset_ids),
                "creators": _creators_to_payload(creators),
                "publisher_facility_code": publisher_facility_code,
                "publication_year": publication_year,
                "license": license_value,
                "occurred_at": occurred_at.isoformat(),
                "registered_by": str(registered_by),
            }
        case EditionDatasetAdded(
            edition_id=edition_id,
            dataset_id=dataset_id,
            occurred_at=occurred_at,
            added_by=added_by,
        ):
            return {
                "edition_id": str(edition_id),
                "dataset_id": str(dataset_id),
                "occurred_at": occurred_at.isoformat(),
                "added_by": str(added_by),
            }
        case EditionDatasetRemoved(
            edition_id=edition_id,
            dataset_id=dataset_id,
            occurred_at=occurred_at,
            removed_by=removed_by,
        ):
            return {
                "edition_id": str(edition_id),
                "dataset_id": str(dataset_id),
                "occurred_at": occurred_at.isoformat(),
                "removed_by": str(removed_by),
            }
        case EditionSealed(
            edition_id=edition_id,
            content_hash=content_hash,
            publisher_facility_code=publisher_facility_code,
            publication_year=publication_year,
            license=license_value,
            sealed_dataset_ids=sealed_dataset_ids,
            occurred_at=occurred_at,
            sealed_by=sealed_by,
        ):
            return {
                "edition_id": str(edition_id),
                "content_hash": content_hash,
                "publisher_facility_code": publisher_facility_code,
                "publication_year": publication_year,
                "license": license_value,
                "sealed_dataset_ids": sorted(str(d) for d in sealed_dataset_ids),
                "occurred_at": occurred_at.isoformat(),
                "sealed_by": str(sealed_by),
            }
        case EditionPublished(
            edition_id=edition_id,
            external_pid_scheme=external_pid_scheme,
            external_pid_value=external_pid_value,
            published_content_hash=published_content_hash,
            occurred_at=occurred_at,
            published_by=published_by,
        ):
            return {
                "edition_id": str(edition_id),
                "external_pid_scheme": external_pid_scheme,
                "external_pid_value": external_pid_value,
                "published_content_hash": published_content_hash,
                "occurred_at": occurred_at.isoformat(),
                "published_by": str(published_by),
            }
        case EditionWithdrawn(
            edition_id=edition_id,
            withdrawal_reason=withdrawal_reason,
            occurred_at=occurred_at,
            withdrawn_by=withdrawn_by,
        ):
            return {
                "edition_id": str(edition_id),
                "withdrawal_reason": withdrawal_reason,
                "occurred_at": occurred_at.isoformat(),
                "withdrawn_by": str(withdrawn_by),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> EditionEvent:
    """Rebuild an Edition event from a `StoredEvent` loaded from the event store.

    Each per-event builder is wrapped in `deserialize_or_raise` to
    surface malformed payloads as `Malformed<EventName>` per the
    from-stored wrap convention.
    """
    payload = stored.payload
    match stored.event_type:
        case "EditionRegistered":

            def _build_registered() -> EditionRegistered:
                return EditionRegistered(
                    edition_id=UUID(payload["edition_id"]),
                    kind=payload["kind"],
                    title=payload["title"],
                    dataset_ids=tuple(UUID(d) for d in payload["dataset_ids"]),
                    creators=_creators_from_payload(payload["creators"]),
                    publisher_facility_code=payload.get("publisher_facility_code"),
                    publication_year=payload.get("publication_year"),
                    license=payload.get("license"),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    registered_by=ActorId(UUID(payload["registered_by"])),
                )

            return deserialize_or_raise("EditionRegistered", _build_registered)
        case "EditionDatasetAdded":

            def _build_added() -> EditionDatasetAdded:
                return EditionDatasetAdded(
                    edition_id=UUID(payload["edition_id"]),
                    dataset_id=UUID(payload["dataset_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    added_by=ActorId(UUID(payload["added_by"])),
                )

            return deserialize_or_raise("EditionDatasetAdded", _build_added)
        case "EditionDatasetRemoved":

            def _build_removed() -> EditionDatasetRemoved:
                return EditionDatasetRemoved(
                    edition_id=UUID(payload["edition_id"]),
                    dataset_id=UUID(payload["dataset_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    removed_by=ActorId(UUID(payload["removed_by"])),
                )

            return deserialize_or_raise("EditionDatasetRemoved", _build_removed)
        case "EditionSealed":

            def _build_sealed() -> EditionSealed:
                return EditionSealed(
                    edition_id=UUID(payload["edition_id"]),
                    content_hash=payload["content_hash"],
                    publisher_facility_code=payload["publisher_facility_code"],
                    publication_year=int(payload["publication_year"]),
                    license=payload.get("license"),
                    sealed_dataset_ids=tuple(UUID(d) for d in payload["sealed_dataset_ids"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    sealed_by=ActorId(UUID(payload["sealed_by"])),
                )

            return deserialize_or_raise("EditionSealed", _build_sealed)
        case "EditionPublished":

            def _build_published() -> EditionPublished:
                return EditionPublished(
                    edition_id=UUID(payload["edition_id"]),
                    external_pid_scheme=payload["external_pid_scheme"],
                    external_pid_value=payload["external_pid_value"],
                    published_content_hash=payload["published_content_hash"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    published_by=ActorId(UUID(payload["published_by"])),
                )

            return deserialize_or_raise("EditionPublished", _build_published)
        case "EditionWithdrawn":

            def _build_withdrawn() -> EditionWithdrawn:
                return EditionWithdrawn(
                    edition_id=UUID(payload["edition_id"]),
                    withdrawal_reason=payload["withdrawal_reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    withdrawn_by=ActorId(UUID(payload["withdrawn_by"])),
                )

            return deserialize_or_raise("EditionWithdrawn", _build_withdrawn)
        case _:
            msg = f"Unknown EditionEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "EditionDatasetAdded",
    "EditionDatasetRemoved",
    "EditionEvent",
    "EditionPublished",
    "EditionRegistered",
    "EditionSealed",
    "EditionWithdrawn",
    "event_type_name",
    "from_stored",
    "to_payload",
]
