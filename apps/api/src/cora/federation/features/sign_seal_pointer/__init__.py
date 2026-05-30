"""Vertical slice for the `SignSealPointer` command.

Module-as-namespace surface, symmetric with the other Federation
transition slices:

    from cora.federation.features import sign_seal_pointer

    cmd = sign_seal_pointer.SignSealPointer(
        facility_id=...,
        new_head_hash=...,
        new_sequence_number=...,
    )
    handler = sign_seal_pointer.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Single-source transition: requires the Seal singleton to be in `Live`
status. Strict-not-idempotent: signing from a non-Live posture raises
`SealCannotSignError` (HTTP 409); supplying a sequence number that does
not strictly exceed the Seal's `current_sequence_number` raises
`SealSequenceNumberRegressionError` (HTTP 409). The aggregate captures
the operator-supplied head hash and sequence number; the evolver
promotes them onto `current_head_hash` and `current_sequence_number`
on apply while leaving the FSM status at `Live`.
"""

from cora.federation.features.sign_seal_pointer import tool
from cora.federation.features.sign_seal_pointer.command import SignSealPointer
from cora.federation.features.sign_seal_pointer.decider import decide
from cora.federation.features.sign_seal_pointer.handler import Handler, bind
from cora.federation.features.sign_seal_pointer.route import router

__all__ = [
    "Handler",
    "SignSealPointer",
    "bind",
    "decide",
    "router",
    "tool",
]
