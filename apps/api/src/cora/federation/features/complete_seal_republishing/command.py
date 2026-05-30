"""The `CompleteSealRepublishing` command: intent dataclass for this slice.

`facility_id` identifies the Seal singleton; the handler derives the
stream UUID deterministically via UUID5 with the federation namespace.
`new_head_hash` and `new_sequence_number` are optional: when supplied
together they refresh the head pointer and bump the monotonic sequence
on the back-edge; when both absent the republish completes without
publishing a fresh head (republish-only-shape change).

Strict-not-idempotent transition: completing a republish on a Seal
that is not in `Republishing` status raises
`SealCannotCompleteRepublishingError` -> HTTP 409. HTTP-layer
idempotency adds no value for transitions; the strict guard at the
decider is the contract.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CompleteSealRepublishing:
    """Operator closes an in-flight republish window (Republishing -> Live).

    Single-source: requires the Seal to be in `Republishing` status.
    Optionally refreshes `current_head_hash` and bumps
    `current_sequence_number` (both must be provided together).
    """

    facility_id: str
    new_head_hash: str | None
    new_sequence_number: int | None
