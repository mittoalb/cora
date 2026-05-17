"""Vertical slice for the `VersionAgent` command."""

from cora.agent.features.version_agent import tool
from cora.agent.features.version_agent.command import VersionAgent
from cora.agent.features.version_agent.decider import decide
from cora.agent.features.version_agent.handler import Handler, bind
from cora.agent.features.version_agent.route import router

__all__ = [
    "Handler",
    "VersionAgent",
    "bind",
    "decide",
    "router",
    "tool",
]
