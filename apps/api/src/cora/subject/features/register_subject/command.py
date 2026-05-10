"""The `RegisterSubject` command — intent dataclass for this slice.

Carries only what the caller controls (the subject's display name).
Server-side concerns (new aggregate id, wall-clock timestamp,
correlation id, per-event ids) are injected by the handler from
infrastructure ports, matching the cross-BC create-style command
shape locked in Access / Trust.

Status is implicit at registration (`Received`) and not part of the
command — see the Subject aggregate's `state.py` docstring for the
enum-in-state, str-in-event convention.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RegisterSubject:
    """Register a new subject with the given display name."""

    name: str
