"""Pure decider for the `DefinePolicy` command.

Pure function: given the current Policy state (None for a fresh
stream) and a `DefinePolicy` command, returns the events to append.
No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler.

Does NOT verify that `conduit_id` references an existing Conduit or
that each `permitted_principals` UUID corresponds to a registered
Actor — see `cora.trust.aggregates.policy.state` for the eventual-
consistency rationale.

Permission sets are converted to `list[UUID]` / `list[str]` for the
event payload (events carry primitives; lists JSON-serialize cleanly
and `to_payload` sorts them deterministically).
"""

from datetime import datetime
from uuid import UUID

from cora.trust.aggregates.policy import (
    Policy,
    PolicyAlreadyExistsError,
    PolicyDefined,
    PolicyName,
)
from cora.trust.features.define_policy.command import DefinePolicy


def decide(
    state: Policy | None,
    command: DefinePolicy,
    *,
    now: datetime,
    new_id: UUID,
) -> list[PolicyDefined]:
    """Decide the events produced by defining a new policy."""
    if state is not None:
        raise PolicyAlreadyExistsError(state.id)
    name = PolicyName(command.name)  # validates + trims
    return [
        PolicyDefined(
            policy_id=new_id,
            name=name.value,
            conduit_id=command.conduit_id,
            permitted_principals=list(command.permitted_principals),
            permitted_commands=list(command.permitted_commands),
            occurred_at=now,
        )
    ]
