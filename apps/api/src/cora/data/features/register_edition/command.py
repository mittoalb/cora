"""The `RegisterEdition` command for the register_edition slice.

Carries everything the caller controls to register a new Edition:
  - `kind`: which serialization-target this Edition uses (closed enum)
  - `title`: display title (1-500 chars)
  - `dataset_ids`: initial member set (>=1; sorted on wire)
  - `creators`: ordered tuple of (actor_id, affiliation) (1-100; order
    is publication-significant)
  - `license`: optional SPDX identifier (free-text, 1-100 chars; if
    supplied at register-time, locked in)
  - `publication_year`: optional explicit year (1900..current_year+5;
    if supplied, locked in; auto-derived at seal-time if not)
  - `publisher_facility_code`: optional publisher Facility code
    (FacilityLookup-validated at seal-time, NOT at register-time)

The new Edition id is server-allocated by the handler from the
IdGenerator port.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CreatorEntry:
    """Boundary-layer creator descriptor (flat, primitives only).

    The decider constructs the typed `Creator` VO from this. Wire
    payload carries `actor_id` as UUID + `affiliation` as optional
    str.
    """

    actor_id: UUID
    affiliation: str | None = None


@dataclass(frozen=True)
class RegisterEdition:
    """Register a new Edition with the given metadata and initial datasets."""

    kind: str
    title: str
    dataset_ids: frozenset[UUID]
    creators: tuple[CreatorEntry, ...]
    license: str | None = None
    publication_year: int | None = None
    publisher_facility_code: str | None = None
