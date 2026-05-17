"""Agent bounded context.

Phase 8f-a (config-only): one aggregate, `Agent`. Genesis aggregate
plus 3-state lifecycle FSM (`Defined -> Versioned -> Deprecated`).
NO LLM, NO runtime, NO Decision integration -- those land in 8f-b
under [[project_run_debrief_design]].

`Agent.id` is SHARED with Access BC's `Actor.id` for the same agent.
`define_agent` writes both `ActorRegistered(kind="agent")` (Access
stream) and `AgentDefined` (Agent stream) atomically via
`EventStore.append_streams`. Mirrors 11a-c-2 `amend_clearance` and
11b-a `supersede_caution` cross-aggregate atomic-write patterns.

Public surface re-exported here:
  - `AgentHandlers`            (handler bundle)
  - `register_agent_routes`    (FastAPI route + exception handler registration)
  - `register_agent_tools`     (MCP tool registration)
  - `wire_agent`               (Kernel -> AgentHandlers factory)
"""

from cora.agent.routes import register_agent_routes
from cora.agent.tools import register_agent_tools
from cora.agent.wire import AgentHandlers, wire_agent

__all__ = [
    "AgentHandlers",
    "register_agent_routes",
    "register_agent_tools",
    "wire_agent",
]
