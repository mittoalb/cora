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
    """Mark an existing Run as aborted (emergency-exit terminal).

    `decided_by_decision_id` (mirrors AdjustRun + StartRun):
    optional Decision BC reference to the record that justified this
    abort (most commonly an OperatorAbortDecision or
    EquipmentAbortDecision per [[project-run-debrief-design]]'s 5-value
    choice enum). Operators can record ad-hoc / emergency aborts
    without a Decision; not every abort needs formal justification.
    NO existence check at the decider per the cross-BC eventual-
    consistency stance.
    """

    run_id: UUID
    reason: str
    decided_by_decision_id: UUID | None = None
