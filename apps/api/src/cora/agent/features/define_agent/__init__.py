"""Vertical slice for the `DefineAgent` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.agent.features import define_agent

    cmd = define_agent.DefineAgent(
        kind="RunDebriefer", name="...", version="v1",
        model_ref=ModelRef(provider="anthropic", model="..."),
    )
    handler = define_agent.bind(deps)
    agent_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.agent.features.define_agent import tool
from cora.agent.features.define_agent.command import DefineAgent
from cora.agent.features.define_agent.decider import decide
from cora.agent.features.define_agent.handler import Handler, IdempotentHandler, bind
from cora.agent.features.define_agent.route import router

__all__ = [
    "DefineAgent",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
