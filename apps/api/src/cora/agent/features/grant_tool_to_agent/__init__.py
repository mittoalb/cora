"""Vertical slice for the `GrantToolToAgent` command (Phase 8f-c iter 2).

Adds one MCP tool to the Agent's allowlist. Idempotent: granting
a tool the Agent already has emits NO event. Source set is
`{Defined, Versioned, Suspended}` (Deprecated is the only blocking
state; operators can fix permissions while paused).

Cardinality cap (`AGENT_TOOLS_MAX_COUNT = 32`) is enforced when
the grant would actually add a new tool.
"""

from cora.agent.features.grant_tool_to_agent import tool
from cora.agent.features.grant_tool_to_agent.command import GrantToolToAgent
from cora.agent.features.grant_tool_to_agent.decider import decide
from cora.agent.features.grant_tool_to_agent.handler import Handler, bind
from cora.agent.features.grant_tool_to_agent.route import router

__all__ = [
    "GrantToolToAgent",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
