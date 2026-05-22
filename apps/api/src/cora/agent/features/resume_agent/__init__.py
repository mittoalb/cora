"""Vertical slice for the `ResumeAgent` command.

Returns a `Suspended` Agent back to `Versioned`. NO `reason` field
by design: the act of resuming is its own signal. Asymmetry with
`suspend_agent` is deliberate (events carry facts; Decisions carry
rationale).
"""

from cora.agent.features.resume_agent import tool
from cora.agent.features.resume_agent.command import ResumeAgent
from cora.agent.features.resume_agent.decider import decide
from cora.agent.features.resume_agent.handler import Handler, bind
from cora.agent.features.resume_agent.route import router

__all__ = [
    "Handler",
    "ResumeAgent",
    "bind",
    "decide",
    "router",
    "tool",
]
