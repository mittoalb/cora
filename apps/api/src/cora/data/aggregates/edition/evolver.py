"""Evolver: replay events to reconstruct Edition state.

Status mapping per event type:
  - EditionRegistered      -> REGISTERED (genesis)
  - EditionDatasetAdded    -> mutate dataset_ids; status unchanged
  - EditionDatasetRemoved  -> mutate dataset_ids; status unchanged
  - EditionSealed          -> SEALED
  - EditionPublished       -> PUBLISHED
  - EditionWithdrawn       -> WITHDRAWN

The terminal ``assert_never`` case forces pyright (and the runtime)
to error if a new event type is added to ``EditionEvent`` without a
matching match arm here.

**Critical invariant** for transition arms: every arm MUST carry
every prior Edition field through. Constructing
`Edition(id=..., kind=..., ...)` without explicitly passing the full
field set would silently WIPE genesis fields. We use `dataclasses.replace`
on the prior state to mutate only the transition-relevant fields.
"""

from collections.abc import Sequence
from dataclasses import replace
from typing import assert_never

from cora.data.aggregates.edition.events import (
    EditionDatasetAdded,
    EditionDatasetRemoved,
    EditionEvent,
    EditionPublished,
    EditionRegistered,
    EditionSealed,
    EditionWithdrawn,
)
from cora.data.aggregates.edition.state import (
    Creator,
    Edition,
    EditionKind,
    EditionStatus,
    EditionTitle,
    SpdxIdentifier,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identifier import PersistentIdentifier, PersistentIdentifierScheme


def _require_state(state: Edition | None, event_name: str) -> Edition:
    if state is None:
        msg = f"Edition evolver: {event_name} requires prior state, got None"
        raise ValueError(msg)
    return state


def evolve(state: Edition | None, event: EditionEvent) -> Edition:
    """Apply one event to the current Edition state."""
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
            _ = state  # EditionRegistered is genesis; prior state ignored.
            rebuilt_creators = tuple(
                Creator(
                    actor_id=entry["actor_id"],
                    affiliation=entry.get("affiliation"),
                )
                for entry in creators
            )
            return Edition(
                id=edition_id,
                kind=EditionKind(kind),
                title=EditionTitle(title),
                dataset_ids=frozenset(dataset_ids),
                creators=rebuilt_creators,
                registered_at=occurred_at,
                registered_by=registered_by,
                status=EditionStatus.REGISTERED,
                publisher_facility_code=(
                    FacilityCode(publisher_facility_code)
                    if publisher_facility_code is not None
                    else None
                ),
                publication_year=publication_year,
                license=(SpdxIdentifier(license_value) if license_value is not None else None),
                content_hash=None,
                external_pid=None,
                sealed_at=None,
                sealed_by=None,
                published_at=None,
                published_by=None,
                withdrawn_at=None,
                withdrawn_by=None,
                withdrawal_reason=None,
            )
        case EditionDatasetAdded(dataset_id=dataset_id):
            prior = _require_state(state, "EditionDatasetAdded")
            return replace(
                prior,
                dataset_ids=prior.dataset_ids | {dataset_id},
            )
        case EditionDatasetRemoved(dataset_id=dataset_id):
            prior = _require_state(state, "EditionDatasetRemoved")
            return replace(
                prior,
                dataset_ids=prior.dataset_ids - {dataset_id},
            )
        case EditionSealed(
            content_hash=content_hash,
            publisher_facility_code=publisher_facility_code,
            publication_year=publication_year,
            license=license_value,
            sealed_dataset_ids=sealed_dataset_ids,
            occurred_at=occurred_at,
            sealed_by=sealed_by,
        ):
            prior = _require_state(state, "EditionSealed")
            return replace(
                prior,
                status=EditionStatus.SEALED,
                dataset_ids=frozenset(sealed_dataset_ids),
                publisher_facility_code=FacilityCode(publisher_facility_code),
                publication_year=publication_year,
                license=(SpdxIdentifier(license_value) if license_value is not None else None),
                content_hash=content_hash,
                sealed_at=occurred_at,
                sealed_by=sealed_by,
            )
        case EditionPublished(
            external_pid_scheme=external_pid_scheme,
            external_pid_value=external_pid_value,
            occurred_at=occurred_at,
            published_by=published_by,
        ):
            prior = _require_state(state, "EditionPublished")
            return replace(
                prior,
                status=EditionStatus.PUBLISHED,
                external_pid=PersistentIdentifier(
                    scheme=PersistentIdentifierScheme(external_pid_scheme),
                    value=external_pid_value,
                ),
                published_at=occurred_at,
                published_by=published_by,
            )
        case EditionWithdrawn(
            withdrawal_reason=withdrawal_reason,
            occurred_at=occurred_at,
            withdrawn_by=withdrawn_by,
        ):
            prior = _require_state(state, "EditionWithdrawn")
            return replace(
                prior,
                status=EditionStatus.WITHDRAWN,
                withdrawal_reason=withdrawal_reason,
                withdrawn_at=occurred_at,
                withdrawn_by=withdrawn_by,
            )
        case _:  # pragma: no cover  # exhaustiveness guard for future arms
            assert_never(event)


def fold(events: Sequence[EditionEvent]) -> Edition | None:
    """Replay a stream of events from the empty initial state."""
    state: Edition | None = None
    for event in events:
        state = evolve(state, event)
    return state


__all__ = ["evolve", "fold"]
