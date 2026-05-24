"""Pure decider for the `SuspendAgent` command.

Source set is `{Versioned}` only. Strict-not-idempotent:
re-suspending a `Suspended` Agent raises `AgentCannotSuspendError`.

## Validation

  - State must not be None -> `AgentNotFoundError`
  - Current status must be `Versioned` -> `AgentCannotSuspendError`
  - `reason` REQUIRED; wrapped via `AgentSuspensionReason(...)`;
    1-500 chars after trim -> `InvalidAgentSuspensionReasonError`.
"""

from datetime import datetime

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotSuspendError,
    AgentNotFoundError,
    AgentStatus,
    AgentSuspended,
    AgentSuspensionReason,
)
from cora.agent.features.suspend_agent.command import SuspendAgent


def decide(
    state: Agent | None,
    command: SuspendAgent,
    *,
    now: datetime,
) -> list[AgentSuspended]:
    """Decide the events produced by suspending an Agent.

    Invariants:
      - State must not be None -> AgentNotFoundError
      - Current status must be Versioned -> AgentCannotSuspendError
      - Reason must be valid -> InvalidAgentSuspensionReasonError
        (via AgentSuspensionReason VO)
    """
    if state is None:
        raise AgentNotFoundError(command.agent_id)
    if state.status is not AgentStatus.VERSIONED:
        raise AgentCannotSuspendError(state.id, state.status)

    reason = AgentSuspensionReason(command.reason)

    return [
        AgentSuspended(
            agent_id=state.id,
            reason=reason.value,
            occurred_at=now,
        )
    ]
