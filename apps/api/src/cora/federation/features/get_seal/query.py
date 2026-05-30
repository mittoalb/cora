"""The `GetSeal` query: intent dataclass for this read slice.

Mirrors `GetCalibration` / `GetPermit` / `GetCredential`: queries are
dataclasses just like commands, naming the read intent and carrying
only what the caller controls. The application handler adds context
(correlation_id, principal_id, surface_id) at call time.

Cross-BC pattern: queries are full vertical slices symmetric with
commands but without a decider (queries don't emit events). The
handler is a thin wrapper around `load_seal` +
`load_seal_timestamps` (Path C composition).

Singleton-per-facility identity: a Seal is keyed on the human-readable
`facility_id` (str), not by a UUID. The handler derives the
deterministic stream UUID via `seal_stream_id(facility_id)` before
loading aggregate state.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GetSeal:
    """Read the current state of the per-facility Seal singleton."""

    facility_id: str
