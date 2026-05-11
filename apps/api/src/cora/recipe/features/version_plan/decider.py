"""Pure decider for the `VersionPlan` command.

Multi-source-state transition: `Defined | Versioned -> Versioned`.
Both Defined (first revision) and Versioned (subsequent revisions)
are valid sources; only Deprecated is rejected.

## Deliberate divergence from strict-not-idempotent

Same as version_practice (Recipe 6d-2), version_method (Recipe 6b),
and version_capability (Equipment 5f-2): re-versioning with the same
tag succeeds and emits a fresh event. Re-attestation is a legitimate
audit moment. Pinned by
`test_decide_allows_versioning_with_same_tag_for_re_attestation`.

Invariants:
  - State must not be None -> PlanNotFoundError
  - command.version_tag must be 1-50 chars after trimming
    -> InvalidPlanVersionTagError
  - State.status must be in {Defined, Versioned}
    -> PlanCannotVersionError(current_status=...)

Note: this decider does NOT re-validate the bind-time invariants
(capability superset, upstream-not-deprecated, no-decommissioned-
asset). Versioning a Plan is a label change on an existing binding,
not a re-bind. Re-validation against current upstream state is the
job of a future ongoing-satisfiability projection (gate-review Q3
deferred option iii').
"""

from datetime import datetime

from cora.recipe.aggregates.plan import (
    PLAN_VERSION_TAG_MAX_LENGTH,
    InvalidPlanVersionTagError,
    Plan,
    PlanCannotVersionError,
    PlanNotFoundError,
    PlanStatus,
    PlanVersioned,
)
from cora.recipe.features.version_plan.command import VersionPlan

_VERSIONABLE_STATUSES: tuple[PlanStatus, ...] = (
    PlanStatus.DEFINED,
    PlanStatus.VERSIONED,
)


def decide(
    state: Plan | None,
    command: VersionPlan,
    *,
    now: datetime,
) -> list[PlanVersioned]:
    """Decide the events produced by versioning an existing plan."""
    if state is None:
        raise PlanNotFoundError(command.plan_id)
    trimmed = command.version_tag.strip()
    if not trimmed or len(trimmed) > PLAN_VERSION_TAG_MAX_LENGTH:
        raise InvalidPlanVersionTagError(command.version_tag)
    if state.status not in _VERSIONABLE_STATUSES:
        raise PlanCannotVersionError(state.id, current_status=state.status)
    return [
        PlanVersioned(
            plan_id=state.id,
            version_tag=trimmed,
            occurred_at=now,
        )
    ]
