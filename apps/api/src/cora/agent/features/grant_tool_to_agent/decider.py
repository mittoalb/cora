"""Pure decider for the `GrantToolToAgent` command.

Source set is `{Defined, Versioned, Suspended}`. Idempotent: a
grant of an already-granted tool returns `[]` (no event). The
cardinality cap (`AGENT_TOOLS_MAX_COUNT`) is enforced only when
the grant would actually add a new entry; idempotent re-grants
of an existing tool against a full set still succeed silently.

## Validation

  - State must not be None -> `AgentNotFoundError`
  - Current status must not be `Deprecated` -> `AgentCannotGrantToolError`
  - `tool_name` wrapped via `ToolName(...)`; 1-100 chars after trim
    -> `InvalidToolNameError`
  - If grant would add a new entry AND projected size would exceed
    `AGENT_TOOLS_MAX_COUNT` -> `InvalidAgentToolsError`
"""

from datetime import datetime

from cora.agent.aggregates.agent import (
    AGENT_TOOLS_MAX_COUNT,
    Agent,
    AgentCannotGrantToolError,
    AgentNotFoundError,
    AgentStatus,
    AgentToolGranted,
    InvalidAgentToolsError,
    ToolName,
)
from cora.agent.features.grant_tool_to_agent.command import GrantToolToAgent


def decide(
    state: Agent | None,
    command: GrantToolToAgent,
    *,
    now: datetime,
) -> list[AgentToolGranted]:
    """Decide the events produced by granting a tool to an Agent.

    Invariants:
      - State must not be None -> AgentNotFoundError
      - Current status must not be Deprecated
        -> AgentCannotGrantToolError
      - Tool name must be valid -> InvalidToolNameError
        (via ToolName VO)
      - Projected tools count must not exceed AGENT_TOOLS_MAX_COUNT
        when adding a new entry -> InvalidAgentToolsError
    """
    if state is None:
        raise AgentNotFoundError(command.agent_id)
    if state.status is AgentStatus.DEPRECATED:
        raise AgentCannotGrantToolError(state.id, state.status)

    tool_name = ToolName(command.tool_name)

    if tool_name in state.tools:
        return []

    if len(state.tools) + 1 > AGENT_TOOLS_MAX_COUNT:
        raise InvalidAgentToolsError(len(state.tools) + 1)

    return [
        AgentToolGranted(
            agent_id=state.id,
            tool_name=tool_name.value,
            occurred_at=now,
        )
    ]
