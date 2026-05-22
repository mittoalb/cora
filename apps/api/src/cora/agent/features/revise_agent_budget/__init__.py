"""Vertical slice for the `ReviseAgentBudget` command.

Revises the Agent's declarative budget caps. Both
`monthly_usd_cap` and `daily_token_cap` are independently
nullable so the same command carries "set both", "set one,
clear the other", "set new monthly, keep daily", and "clear
all" cases. When both fields are None the Agent's `budget`
field is set to None.

Idempotent: a revise that produces the same effective budget
as the current one emits NO event.

Source set is `{Defined, Versioned, Suspended}` (Deprecated is
the only blocking state; operators can fix budget while paused).

Enforcement is deferred to 8h Budget BC adoption: at iter 2
these are declaration-only fields.
"""

from cora.agent.features.revise_agent_budget import tool
from cora.agent.features.revise_agent_budget.command import ReviseAgentBudget
from cora.agent.features.revise_agent_budget.decider import decide
from cora.agent.features.revise_agent_budget.handler import Handler, bind
from cora.agent.features.revise_agent_budget.route import router

__all__ = [
    "Handler",
    "ReviseAgentBudget",
    "bind",
    "decide",
    "router",
    "tool",
]
