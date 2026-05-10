"""The `EvaluatePolicy` query — intent dataclass for this read slice.

Asks "does Policy P permit `subject_principal_id` to issue
`subject_command_name` via `subject_conduit_id`?". The handler loads
the Policy via `load_policy` and delegates to the pure
`evaluate(policy, ...)` function in the aggregate.

Field naming: `subject_*` prefix disambiguates the SUBJECT of the
authorization check from the CALLER making the query (the caller
arrives via the cross-BC `principal_id` handler kwarg). Without the
prefix, `query.principal_id` and the handler's `principal_id` kwarg
would be the same name with different meaning at every handler call
site. The prefix surfaces the distinction at the field level so it
cannot be accidentally conflated.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class EvaluatePolicy:
    """Evaluate a specific Policy against a (principal, command, conduit) tuple."""

    policy_id: UUID
    subject_principal_id: UUID
    subject_command_name: str
    subject_conduit_id: UUID
