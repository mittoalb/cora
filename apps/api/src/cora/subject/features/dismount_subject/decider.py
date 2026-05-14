"""Pure decider for the `DismountSubject` command (Phase 4f).

Inverse of `mount_subject` for the physical-mount fact:
`Mounted | Measured -> Received` with `mounted_on_asset_id` cleared.
Distinct from `remove_subject` which is terminal-leading; dismount
keeps the Subject pre-terminal so a subsequent `mount_subject` can
fire again (multi-stage workflow).

Invariants:
  - State must not be None -> SubjectNotFoundError
  - State.status must be in {Mounted, Measured}
    -> SubjectCannotDismountError(current_status=...)

Strict semantics, not idempotent: dismounting a Subject that isn't
currently mounted (Received, Removed, terminal states) raises.
Matches the 5g-c / 5g-b precedent of explicit-state-check before
emit (rather than no-op-on-unchanged) because dismount represents
a discrete physical operator action that should appear in the audit
log if invoked.

`from_asset_id` is read from prior state's `mounted_on_asset_id`,
guaranteed non-None when status is in {Mounted, Measured} per 4b's
invariant (mount sets it; subsequent measure preserves it).
"""

from datetime import datetime

from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotDismountError,
    SubjectDismounted,
    SubjectNotFoundError,
    SubjectStatus,
)
from cora.subject.features.dismount_subject.command import DismountSubject

_DISMOUNTABLE_STATES: tuple[SubjectStatus, ...] = (
    SubjectStatus.MOUNTED,
    SubjectStatus.MEASURED,
)


def decide(
    state: Subject | None,
    command: DismountSubject,
    *,
    now: datetime,
) -> list[SubjectDismounted]:
    """Decide the events produced by dismounting an existing Subject."""
    if state is None:
        raise SubjectNotFoundError(command.subject_id)
    if state.status not in _DISMOUNTABLE_STATES:
        raise SubjectCannotDismountError(state.id, current_status=state.status)
    # Guaranteed non-None per 4b invariant: mount sets mounted_on_asset_id;
    # measure preserves it; only mount/dismount/remove/terminal change it.
    # Defensive assertion documents the invariant.
    assert state.mounted_on_asset_id is not None, (
        f"Subject {state.id} is in status {state.status.value} but has "
        f"mounted_on_asset_id=None; aggregate invariant violated"
    )
    return [
        SubjectDismounted(
            subject_id=state.id,
            from_asset_id=state.mounted_on_asset_id,
            reason=command.reason,
            occurred_at=now,
        )
    ]
