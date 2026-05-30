"""The `RevokePermit` command: intent dataclass for this slice.

`permit_id` is the target Permit aggregate. The principal-id of the
invoker is supplied separately by the application handler at call
time and stamped onto the `PermitRevoked` event as
`revoked_by_actor_id`; revoke is operator-driven and carries no
additional payload.

Closing the permit is terminal: any non-Revoked status transitions to
Revoked. The PermitRevoked event payload does not capture a free-text
reason today; if an audit-narrative breadcrumb is needed in the
future, add it as an aggregate-level field (events.py + evolver.py)
first, then surface it on this command. Until then this slice rejects
extra payload at the schema boundary so callers do not silently lose
audit context.
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
