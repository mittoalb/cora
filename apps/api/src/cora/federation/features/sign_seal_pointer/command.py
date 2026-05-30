"""The `SignSealPointer` command: intent dataclass for this slice.

`facility_id` is the per-facility singleton identity. `new_head_hash`
is the SHA-256 (lowercase hex) of the canonicalized head pointer body
just signed. `new_sequence_number` is the monotonic counter for the
signed pointer chain; the decider rejects values that do not strictly
exceed `state.current_sequence_number` via
`SealSequenceNumberRegressionError`.

The invoking principal's id is supplied separately by the application
handler at call time and stamped onto the emitted event as
`signed_by_actor_id`. The wall-clock `signed_at` payload field is
captured by the handler from `deps.clock.now()` per the non-determinism
principle (capture, don't recompute).

Strict-not-idempotent transition: signing from a non-Live posture
raises `SealCannotSignError` (HTTP 409); supplying a sequence number
that does not strictly exceed the prior raises
`SealSequenceNumberRegressionError` (HTTP 409).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SignSealPointer:
    """Operator signs a new head pointer on the Live singleton (Live -> Live).

    Single-source: requires the Seal to be in `Live` status. The
    decider bumps `current_head_hash` to `new_head_hash` and
    `current_sequence_number` to `new_sequence_number` (which MUST
    strictly exceed the prior value).
    """

    facility_id: str
    new_head_hash: str
    new_sequence_number: int
