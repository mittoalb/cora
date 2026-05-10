"""The `DefineZone` command — intent dataclass for this slice.

Carries only what the caller controls (the zone name). Server-side
concerns (new aggregate id, wall-clock timestamp, correlation id,
per-event ids) are injected by the handler from infrastructure ports,
matching the cross-BC create-style command shape locked in Access.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DefineZone:
    """Define a new Trust zone with the given display name."""

    name: str
