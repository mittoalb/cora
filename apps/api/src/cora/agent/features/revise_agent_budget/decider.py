"""Pure decider for the `ReviseAgentBudget` command.

PUT-semantics: the supplied caps ARE the post-revision budget.
Source set is `{Defined, Versioned, Suspended}`. Idempotent: a
revise that produces the same effective budget as the current
one returns `[]`.

## Validation

  - State must not be None -> `AgentNotFoundError`
  - Current status must not be `Deprecated`
    -> `AgentCannotReviseBudgetError`
  - When at least one of the caps is non-None, the resulting
    pair is wrapped via `AgentBudget(...)`; negative caps
    -> `InvalidAgentBudgetError` (the at-least-one-set
    invariant is satisfied by construction in the same branch).
  - When both caps are None the result is `Agent.budget = None`
    (no VO construction; clearing is always valid).
"""

from datetime import datetime

from cora.agent.aggregates.agent import (
    Agent,
    AgentBudget,
    AgentBudgetRevised,
    AgentCannotReviseBudgetError,
    AgentNotFoundError,
    AgentStatus,
)
from cora.agent.features.revise_agent_budget.command import ReviseAgentBudget


def decide(
    state: Agent | None,
    command: ReviseAgentBudget,
    *,
    now: datetime,
) -> list[AgentBudgetRevised]:
    """Decide the events produced by revising an Agent's budget.

    Invariants:
      - State must not be None -> AgentNotFoundError
      - Current status must not be Deprecated
        -> AgentCannotReviseBudgetError
      - When any cap is non-None, the resulting budget must be valid
        -> InvalidAgentBudgetError (via AgentBudget VO)
    """
    if state is None:
        raise AgentNotFoundError(command.agent_id)
    if state.status is AgentStatus.DEPRECATED:
        raise AgentCannotReviseBudgetError(state.id, state.status)

    # Construct the projected post-revision shape eagerly so any
    # invariant violation (negative caps) fires before idempotency
    # short-circuiting. Clearing branch skips the VO (both None
    # is the no-budget shape, not an AgentBudget value).
    projected: AgentBudget | None
    if command.monthly_usd_cap is None and command.daily_token_cap is None:
        projected = None
    else:
        projected = AgentBudget(
            monthly_usd_cap=command.monthly_usd_cap,
            daily_token_cap=command.daily_token_cap,
        )

    if projected == state.budget:
        return []

    return [
        AgentBudgetRevised(
            agent_id=state.id,
            monthly_usd_cap=command.monthly_usd_cap,
            daily_token_cap=command.daily_token_cap,
            occurred_at=now,
        )
    ]
