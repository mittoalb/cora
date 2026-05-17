"""Vertical slice for the `GetAgent` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.agent.features import get_agent

    q = get_agent.GetAgent(agent_id=...)
    handler = get_agent.bind(deps)
    agent = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.agent.features.get_agent import tool
from cora.agent.features.get_agent.handler import Handler, bind
from cora.agent.features.get_agent.query import GetAgent
from cora.agent.features.get_agent.route import router

__all__ = [
    "GetAgent",
    "Handler",
    "bind",
    "router",
    "tool",
]
