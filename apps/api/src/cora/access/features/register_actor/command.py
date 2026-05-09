"""The `RegisterActor` command — intent dataclass for this slice.

Carries only what the caller controls. Server-side concerns
(new aggregate id, wall-clock timestamp, correlation id, command-instance id)
are injected by the handler from infrastructure ports.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RegisterActor:
    """Register a new actor with the given display name."""

    name: str
