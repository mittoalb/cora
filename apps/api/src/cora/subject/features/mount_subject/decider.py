"""Pure decider for the `MountSubject` command.

Update-style decider with cross-aggregate validation: receives the
rebuilt `Subject` state PLUS a pre-loaded `MountSubjectContext`
carrying the mount-target Asset. Returns the events to append. No
I/O.

Invariants:
  - State must not be None (subject must exist)
    -> SubjectNotFoundError
  - State must be in `Received` (only state from which mount is valid)
    -> SubjectCannotMountError(current_status=...)
  - context.asset must be in `Active` lifecycle
    -> SubjectMountTargetUnavailableError(asset_id, current_lifecycle)

Strict semantics, not idempotent: mounting an already-mounted (or
otherwise non-Received) subject raises `SubjectCannotMountError`.
Idempotency-Key already provides retry safety; the domain stays
explicit.

Cross-aggregate validation pattern per CONTRIBUTING.md: the handler
pre-loads the Asset (existence check raises Equipment's
`AssetNotFoundError` -> 404); the decider stays pure and validates
the Asset's lifecycle as plain data.
"""

from datetime import datetime

from cora.equipment.aggregates.asset import AssetLifecycle
from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotMountError,
    SubjectMounted,
    SubjectMountTargetUnavailableError,
    SubjectNotFoundError,
    SubjectStatus,
)
from cora.subject.features.mount_subject.command import MountSubject
from cora.subject.features.mount_subject.context import MountSubjectContext


def decide(
    state: Subject | None,
    command: MountSubject,
    context: MountSubjectContext,
    *,
    now: datetime,
) -> list[SubjectMounted]:
    """Decide the events produced by mounting an existing subject."""
    if state is None:
        raise SubjectNotFoundError(command.subject_id)
    if state.status is not SubjectStatus.RECEIVED:
        raise SubjectCannotMountError(state.id, current_status=state.status)
    if context.asset.lifecycle is not AssetLifecycle.ACTIVE:
        raise SubjectMountTargetUnavailableError(
            subject_id=state.id,
            asset_id=context.asset.id,
            current_lifecycle=context.asset.lifecycle.value,
        )
    return [
        SubjectMounted(
            subject_id=state.id,
            asset_id=context.asset.id,
            occurred_at=now,
        )
    ]
