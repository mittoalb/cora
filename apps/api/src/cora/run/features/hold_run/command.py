"""The `HoldRun` command — intent dataclass for this slice.

Single-source pause transition: `Running -> Held`. Single-field
command (just run_id); no body at the API layer. Hold ⇄ Resume
is a bidirectional cycle with unlimited repeats — no domain reason
field on Hold (matches PackML / Bluesky precedent that pause is a
routine operation).

Per-event timestamping (`occurred_at`) and the new event id are
injected by the handler from infrastructure ports — same capture-
don't-recompute principle as every other slice.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class HoldRun:
    """Pause an actively-running Run (Running → Held)."""

    run_id: UUID
