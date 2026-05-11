"""The `CompleteRun` command — intent dataclass for this slice.

Single-source happy-path terminal: `Running -> Completed`. Single-
field command (just run_id); no body at the API layer. Mirrors the
shape of `DeprecatePlan` / `DeprecatePractice` / `DeprecateMethod`
(other terminal-without-payload commands).

Per-event timestamping (`occurred_at`) and the new event id are
injected by the handler from infrastructure ports — same capture-
don't-recompute principle as every other slice.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CompleteRun:
    """Mark an existing Run as completed (happy-path terminal)."""

    run_id: UUID
