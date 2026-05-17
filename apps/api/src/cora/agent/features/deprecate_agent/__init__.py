"""Vertical slice for the `DeprecateAgent` command."""

from cora.agent.features.deprecate_agent import tool
from cora.agent.features.deprecate_agent.command import DeprecateAgent
from cora.agent.features.deprecate_agent.decider import decide
from cora.agent.features.deprecate_agent.handler import Handler, bind
from cora.agent.features.deprecate_agent.route import router

__all__ = [
    "DeprecateAgent",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
