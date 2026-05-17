"""Vertical slice for the `SuspendAgent` command (Phase 8f-c iter 2).

Operator-pause from `Versioned -> Suspended`. Non-terminal: returns
via `resume_agent`. `reason` is REQUIRED (high-information signal
that the audit log should always carry context for).
"""

from cora.agent.features.suspend_agent import tool
from cora.agent.features.suspend_agent.command import SuspendAgent
from cora.agent.features.suspend_agent.decider import decide
from cora.agent.features.suspend_agent.handler import Handler, bind
from cora.agent.features.suspend_agent.route import router

__all__ = [
    "Handler",
    "SuspendAgent",
    "bind",
    "decide",
    "router",
    "tool",
]
