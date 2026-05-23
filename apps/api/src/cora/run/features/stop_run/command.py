"""The `StopRun` command — intent dataclass for this slice.

Multi-source controlled-exit terminal: `Running | Held -> Stopped`.
Carries operator-supplied free-form `reason` string (1-500 chars
after trim; validated at the API boundary AND defensively at the
decider via `RunStopReason` VO). Mirrors `AbortRun.reason` shape.

Distinct from abort: stop = controlled exit, data valid up to the
stop point; abort = emergency exit, data flagged as potentially
invalid (PackML + Bluesky lifecycle-layer distinction). Substream
cleanup semantics materialize later.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class StopRun:
    """Controlled early exit of a Run (Running | Held → Stopped)."""

    run_id: UUID
    reason: str
