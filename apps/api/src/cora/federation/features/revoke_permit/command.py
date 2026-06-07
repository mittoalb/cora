"""The `RevokePermit` command: intent dataclass for this slice.

`permit_id` is the target Permit aggregate. `reason` is operator-
supplied free text captured at the API boundary for audit-log
breadcrumb purposes (for example, "peer facility decommissioned",
"credential compromise"). `reason` flows through to the emitted
`PermitRevoked` event payload so operator context survives on the
immutable event log.

The principal-id of the invoker is supplied separately by the
application handler at call time and stamped onto the
`PermitRevoked` event as `revoked_by`.

Closing the permit is terminal: any non-Revoked status transitions to
Revoked.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RevokePermit:
    """Operator revokes a Permit (terminal: any non-Revoked -> Revoked).

    Widest-source transition: any of Defined, Active, or Suspended
    transitions to Revoked. Strict-not-idempotent: revoking an
    already-Revoked permit raises `PermitCannotRevokeError`.
    """

    permit_id: UUID
    reason: str | None = None
