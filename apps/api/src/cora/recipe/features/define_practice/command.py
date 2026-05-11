"""The `DefinePractice` command — intent dataclass for this slice.

Carries the caller-controlled inputs:
  - `name` — display name for the new Practice
  - `method_id` — the Method this Practice adapts (eventual-
    consistency stance: existence not verified at decide time,
    mismatch surfaces at Plan binding in 6e)
  - `site_id` — the Site-level Asset this Practice belongs to
    (eventual-consistency: existence and level not verified)

Server-side concerns (new aggregate id, wall-clock timestamp,
correlation id, per-event ids) are injected by the handler from
infrastructure ports.

Status is implicit at definition (`Defined`) and not part of the
command — see Practice aggregate's `state.py` docstring for the
enum-in-state, derived-from-event-type-in-evolver convention.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DefinePractice:
    """Define a new facility-adapted Method (Practice)."""

    name: str
    method_id: UUID
    site_id: UUID
