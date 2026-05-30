"""The `ActivatePermit` command: intent dataclass for this slice.

`permit_id` is the target Permit aggregate. The invoking principal's
id is supplied separately by the application handler at call time
(envelope `principal_id` denorms to `activated_by_actor_id` on the
emitted event).

Strict-not-idempotent transition: re-activating an already-Active
permit raises `PermitCannotActivateError` -> HTTP 409. HTTP-layer
idempotency adds no value for transitions; the strict guard at the
decider is the contract.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ActivatePermit:
    """Operator activates a Defined permit (Defined -> Active).

    Single-source: requires the Permit to be in `Defined` status.
    """

    permit_id: UUID
