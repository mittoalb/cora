"""The `AbortRun` command — intent dataclass for this slice.

Single-source emergency-exit terminal: `Running -> Aborted`. Carries
operator-supplied free-form `reason` string (1-500 chars after trim;
validated at the API boundary AND defensively at the decider via
`RunAbortReason` VO). Mirrors `VersionPlan.version_tag` shape for a
string-payload command.

Why free-form vs. structured taxonomy: locked at the 6f-2 gate review
as "kept open with documented re-evaluation triggers" rather than
prematurely categorized. See `InvalidRunAbortReasonError` docstring
for the three trigger conditions that would justify revisiting.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AbortRun:
    """Mark an existing Run as aborted (emergency-exit terminal)."""

    run_id: UUID
    reason: str
