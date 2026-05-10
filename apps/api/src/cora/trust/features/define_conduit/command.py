"""The `DefineConduit` command — intent dataclass for this slice.

Carries what the caller controls: the conduit's display name and the
two endpoint zone IDs. Server-side concerns (new aggregate id, wall-
clock timestamp, correlation id, per-event ids) are injected by the
handler from infrastructure ports.

`source_zone_id` and `target_zone_id` are stored as bare UUIDs; the
decider does NOT verify the referenced Zones exist. See the Conduit
aggregate's `state.py` docstring for the eventual-consistency
rationale.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DefineConduit:
    """Define a new Trust conduit between two zones."""

    name: str
    source_zone_id: UUID
    target_zone_id: UUID
