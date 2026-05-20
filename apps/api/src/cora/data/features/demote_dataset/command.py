"""The `DemoteDataset` command — intent dataclass for this slice.

Demotes a Dataset from `Production` intent to `Retracted` intent
(terminal Intent value). Carries the target dataset's id plus an
operator-supplied free-form `reason` string (1-500 chars after trim;
validated at the API boundary AND defensively at the decider via the
`DemotionReason` VO).

Operationally: this is the operator saying "this dataset's authoritative
status is being retracted — discovered calibration error, methodology
challenged in peer review, sample compromised post-hoc, etc." The audit
trail records WHY immutably. Mirrors the Crossref retraction model
(additive notice, original DatasetPromoted event preserved + marked).

Strict-not-idempotent: re-demoting an already-Retracted Dataset raises
`DatasetAlreadyRetractedError` (mirrors promote_dataset / discard_dataset
strict-not-idempotent semantics + every other terminal-mutation pattern
in the codebase).

Source-state constraint: must be currently Production. Demoting Trial
raises `DatasetCannotDemoteError` (semantically meaningless; use
discard_dataset for never-authoritative cleanup). Demoting Discarded
raises `DatasetCannotDemoteError` (Discarded is a stronger terminal;
bytes already gone). See [[project-dataset-demote-design]].

Decision linkage is OPTIONAL: this command does NOT carry a
`decided_by_decision_id`. Operators can demote without a Decision
(quick retraction during incident response). Audit-grade demotion
includes a paired Decision with `override_kind="invalidation"` +
`parent_id` pointing at the prior promote-driving Decision, written
via a separate `register_decision` call before/after this command.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DemoteDataset:
    """Demote an existing Dataset (Production intent → Retracted intent)."""

    dataset_id: UUID
    reason: str
