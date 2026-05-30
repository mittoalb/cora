"""The `DecommissionFrame` command - intent dataclass.

Update-style: targets an existing Frame by `frame_id`. Carries an
operator-supplied `reason` (free text, audit-only). The handler
loads the `frame_consumers` projection precondition before calling
the decider; if any active Mount or child Frame still references
this frame, the handler raises `FrameInUseError` without emitting
an event.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DecommissionFrame:
    """Decommission an existing frame (terminal lifecycle)."""

    frame_id: UUID
    reason: str
