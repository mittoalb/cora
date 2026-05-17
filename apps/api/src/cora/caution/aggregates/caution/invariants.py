"""Caution aggregate invariants as pure predicates.

Shared kernel for the Caution BC's load-bearing predicates that
must hold at every write site. Hoisted here so callers (the BC's
own deciders AND cross-BC writers like
`cora.agent.features.promote_caution_proposal`) call the same
function instead of re-implementing the check.

Cross-BC writers are permitted to import from `cora.caution.aggregates.*`
per tach rule 2; the `features.*` namespace stays off-limits. This
module IS that public-surface invariant API.

Each function raises the canonical error from `aggregates.caution.state`
on violation and returns `None` on success. Keep them parametrically
pure (input -> raise-or-pass); no implicit defaults, no IO.

Regression context: commit `cfc9540` restored the supersede
target-stability check on the cross-BC write after the Pattern C
refactor in `b6c8e0a` dropped it. That regression class is now
structurally prevented: any caller constructing a `CautionSuperseded`
+ child `CautionRegistered` pair should call
`ensure_target_preserved` here, and the architecture test in
`tests/architecture/test_caution_invariants_module.py` pins it.
"""

from datetime import datetime

from cora.caution.aggregates.caution.state import (
    Caution,
    CautionCannotSupersedeError,
    CautionStatus,
    CautionTarget,
    InvalidCautionExpiresAtError,
    InvalidCautionSupersedeTargetError,
)

_SUPERSEDABLE_STATUSES: tuple[CautionStatus, ...] = (CautionStatus.ACTIVE,)


def ensure_supersedable(parent: Caution) -> None:
    """Parent must be Active to be superseded."""
    if parent.status not in _SUPERSEDABLE_STATUSES:
        raise CautionCannotSupersedeError(parent.id, parent.status)


def ensure_target_preserved(parent_target: CautionTarget, child_target: CautionTarget) -> None:
    """Supersession preserves target; retargeting forces a fresh caution."""
    if child_target != parent_target:
        raise InvalidCautionSupersedeTargetError(
            "supersede preserves target; start a new caution to retarget"
        )


def ensure_expires_at_future(expires_at: datetime | None, now: datetime) -> None:
    """If supplied, expires_at must be strictly in the future relative to now."""
    if expires_at is not None and expires_at <= now:
        raise InvalidCautionExpiresAtError("expires_at must be in the future")
