"""Pure decider for the `DeprecateAgent` command.

Source set is `{Defined, Versioned, Suspended}` — `Suspended` is
in the set so an operator who paused an agent can still retire it
without resuming first. Strict-not-idempotent: re-
deprecating an already-Deprecated Agent raises
`AgentCannotDeprecateError`.

## Validation

  - State must not be None -> `AgentNotFoundError`
  - Current status must be `Defined`, `Versioned`, or `Suspended` ->
    `AgentCannotDeprecateError`
  - `reason` wrapped via `AgentDeprecationReason(...)` when not None;
    1-500 chars after trim -> `InvalidAgentDeprecationReasonError`.
    None is allowed.
"""

from datetime import datetime

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotDeprecateError,
    AgentDeprecated,
    AgentDeprecationReason,
    AgentNotFoundError,
    AgentStatus,
)
from cora.agent.features.deprecate_agent.command import DeprecateAgent

_DEPRECATABLE_STATUSES: tuple[AgentStatus, ...] = (
    AgentStatus.DEFINED,
    AgentStatus.VERSIONED,
    AgentStatus.SUSPENDED,
)


def decide(
    state: Agent | None,
    command: DeprecateAgent,
    *,
    now: datetime,
) -> list[AgentDeprecated]:
    """Decide the events produced by deprecating an Agent."""
    if state is None:
        raise AgentNotFoundError(command.agent_id)
    if state.status not in _DEPRECATABLE_STATUSES:
        raise AgentCannotDeprecateError(state.id, state.status)

    reason: AgentDeprecationReason | None = None
    if command.reason is not None:
        reason = AgentDeprecationReason(command.reason)

    return [
        AgentDeprecated(
            agent_id=state.id,
            reason=reason.value if reason is not None else None,
            occurred_at=now,
        )
    ]
