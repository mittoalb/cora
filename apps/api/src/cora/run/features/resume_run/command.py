"""The `ResumeRun` command — intent dataclass for this slice.

Single-source resume transition: `Held -> Running`. Single-field
command (just run_id); no body at the API layer. The inverse of
hold_run. No reason field — resume is just permission to proceed.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ResumeRun:
    """Resume a held Run (Held → Running)."""

    run_id: UUID
