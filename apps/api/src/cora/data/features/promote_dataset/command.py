"""The `PromoteDataset` command — intent dataclass for this slice.

Promotes a Dataset from `Trial` intent to `Production` intent. Carries
the target dataset's id plus an operator-supplied free-form `reason`
string (1-500 chars after trim; validated at the API boundary AND
defensively at the decider via the `PromotionReason` VO).

Operationally: this is the operator saying "this Dataset is the
keeper — publication-grade, citable, used in a paper". The audit
trail records WHY immutably.

Strict-not-idempotent: re-promoting an already-Production Dataset
raises (mirrors discard_dataset's strict-not-idempotent semantics
and every other terminal-mutation pattern in the codebase). See
[[project_dataset_lineage_design]].
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class PromoteDataset:
    """Promote an existing Dataset (Trial intent → Production intent)."""

    dataset_id: UUID
    reason: str
