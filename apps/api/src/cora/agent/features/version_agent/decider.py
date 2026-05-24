"""Pure decider for the `VersionAgent` command.

Single-source transition: `Defined -> Versioned`. Strict-not-idempotent.

## Validation

  - State must not be None -> `AgentNotFoundError`
  - Current status must be `Defined` -> `AgentCannotVersionError`
"""

from datetime import datetime

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotVersionError,
    AgentNotFoundError,
    AgentStatus,
    AgentVersioned,
)
from cora.agent.features.version_agent.command import VersionAgent

_VERSIONABLE_STATUSES: tuple[AgentStatus, ...] = (AgentStatus.DEFINED,)


def decide(
    state: Agent | None,
    command: VersionAgent,
    *,
    now: datetime,
) -> list[AgentVersioned]:
    """Decide the events produced by versioning a Defined Agent.

    Invariants:
      - State must not be None -> AgentNotFoundError
      - Current status must be Defined -> AgentCannotVersionError
    """
    if state is None:
        raise AgentNotFoundError(command.agent_id)
    if state.status not in _VERSIONABLE_STATUSES:
        raise AgentCannotVersionError(state.id, state.status)

    return [
        AgentVersioned(
            agent_id=state.id,
            version=state.version.value,
            occurred_at=now,
        )
    ]
