"""Pure decider for the `SignSealPointer` command.

Single-source transition: `Live -> Live` (the FSM status is unchanged;
`current_head_hash` and `current_sequence_number` advance). Strict-not-
idempotent (matches the Calibration / Clearance / Supply / Permit
precedent): signing from a non-Live posture raises
`SealCannotSignError`.

`signed_by_actor_id` and `now` are handler-injected per the non-
determinism principle (capture, don't recompute); the decider is pure:
state + command + injected non-determinism in, events out. The
`signed_at` payload field on the emitted event reuses `now` so the
projection's `last_signed_at` reflects the same wall-clock the envelope
captured (mirrors Calibration revision `established_at`).

## Validation

  - State must not be None (Seal must exist for this facility)
    -> SealNotFoundError
  - Current status must be `Live`
    -> SealCannotSignError
  - `new_head_hash` must be non-empty after trimming
    -> ValueError
  - `new_sequence_number` must strictly exceed the prior value
    -> SealSequenceNumberRegressionError
"""

from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.seal import (
    Seal,
    SealCannotSignError,
    SealNotFoundError,
    SealPointerSigned,
    SealSequenceNumberRegressionError,
    SealStatus,
)
from cora.federation.features.sign_seal_pointer.command import SignSealPointer


def decide(
    state: Seal | None,
    command: SignSealPointer,
    *,
    now: datetime,
    signed_by_actor_id: UUID,
) -> list[SealPointerSigned]:
    """Decide the events produced by signing a new head pointer on a Live Seal.

    Invariants:
      - State must not be None -> SealNotFoundError
      - Current status must be Live -> SealCannotSignError
      - new_head_hash must be non-empty after trimming -> ValueError
      - new_sequence_number must strictly exceed prior
        -> SealSequenceNumberRegressionError
    """
    if state is None:
        raise SealNotFoundError(command.facility_id)
    if state.status is not SealStatus.LIVE:
        raise SealCannotSignError(state.facility_id, state.status)

    head_hash = command.new_head_hash.strip()
    if not head_hash:
        msg = "new_head_hash must be a non-empty string after trimming"
        raise ValueError(msg)

    if command.new_sequence_number <= state.current_sequence_number:
        raise SealSequenceNumberRegressionError(
            facility_id=state.facility_id,
            prior_sequence_number=state.current_sequence_number,
            proposed_sequence_number=command.new_sequence_number,
        )

    return [
        SealPointerSigned(
            facility_id=state.facility_id,
            head_hash=head_hash,
            sequence_number=command.new_sequence_number,
            signed_at=now,
            signed_by_actor_id=signed_by_actor_id,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
