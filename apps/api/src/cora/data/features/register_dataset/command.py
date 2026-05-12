"""The `RegisterDataset` command, intent dataclass for this slice.

Carries everything the caller controls: identity-free metadata
(name, uri, checksum, byte_size, format) plus the optional cross-
aggregate refs (producing_run_id, subject_id, derived_from). The
new Dataset id is server-allocated by the handler from the
IdGenerator port (matches every other create-style slice in the
codebase).

"Register" rather than "define": the data exists in the world and
we are recording it (URI + checksum + byte_size all describe an
already-existing artefact). Same convention as `register_actor`,
`register_subject`, `register_asset`.

## Optional cross-refs

  - `producing_run_id`: the Run that produced this Dataset. None
    for externally-sourced data, uploaded reference sets, or any
    Dataset registered without a Run context.
  - `subject_id`: the Subject the Dataset is "about." None for
    calibration / dark-field / synthetic data with no sample.
  - `derived_from`: lineage edges to other Datasets this one was
    derived from. Empty for raw/captured data; non-empty for
    derivations (raw → reconstructed → segmented → ...).

All three are validated by the handler at load time (existence
only, no status check; gate-review Q2 lock B).

## Format shape

`media_type` is a loose MIME-type-ish string; `conforms_to` is a
possibly-empty set of profile URIs the Dataset claims to conform
to (NeXus, OME-Zarr, CIF, etc.). Per gate-review L3 refinement
(post-standards-survey), this is structured-from-day-1 to avoid
a breaking change later when one Dataset claims multiple profiles.
"""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class RegisterDataset:
    """Register a new Dataset with the given metadata."""

    name: str
    uri: str
    checksum_algorithm: str
    checksum_value: str
    byte_size: int
    media_type: str
    conforms_to: frozenset[str] = field(default_factory=frozenset[str])
    producing_run_id: UUID | None = None
    subject_id: UUID | None = None
    derived_from: frozenset[UUID] = field(default_factory=frozenset[UUID])
