"""Pure decider for the `ResumeAgent` command.

Source set is `{Suspended}` only. Strict-not-idempotent: resuming
a `Versioned` / `Defined` / `Deprecated` Agent raises
`AgentCannotResumeError`.

## Validation

  - State must not be None -> `AgentNotFoundError`
  - Current status must be `Suspended` -> `AgentCannotResumeError`
"""

from datetime import datetime

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotResumeError,
    AgentNotFoundError,
    AgentResumed,
    AgentStatus,
)
from cora.agent.features.resume_agent.command import ResumeAgent


def decide(
    state: Agent | None,
    command: ResumeAgent,
    *,
    now: datetime,
) -> list[AgentResumed]:
    """Decide the events produced by resuming an Agent."""
    if state is None:
        raise AgentNotFoundError(command.agent_id)
    if state.status is not AgentStatus.SUSPENDED:
        raise AgentCannotResumeError(state.id, state.status)

    return [
        AgentResumed(
            agent_id=state.id,
            occurred_at=now,
        )
    ]
