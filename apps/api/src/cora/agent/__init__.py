"""Agent bounded context.

Phase 8f-a (config-only): one aggregate, `Agent`. Genesis aggregate
plus 3-state lifecycle FSM (`Defined -> Versioned -> Deprecated`).

Phase 8f-b iter 2a (infrastructure): production `AnthropicLLMAdapter`
ships at `cora.agent.adapters.AnthropicLLMAdapter` and is wired into
the Kernel via `build_llm` (composition-root binding lives in
`cora.api.main`). The subscriber that consumes it (RunDebrief)
lands at 8f-b iter 2b.

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
  - `build_llm`                (LLMFactory for `build_kernel`)
"""

from cora.agent._projections import register_agent_projections
from cora.agent._subscribers import register_agent_subscribers
from cora.agent.llm_factory import build_llm
from cora.agent.routes import register_agent_routes
from cora.agent.seed import seed_run_debrief_agent
from cora.agent.seed_caution_drafter import seed_caution_drafter_agent
from cora.agent.tools import register_agent_tools
from cora.agent.wire import AgentHandlers, wire_agent

__all__ = [
    "AgentHandlers",
    "build_llm",
    "register_agent_projections",
    "register_agent_routes",
    "register_agent_subscribers",
    "register_agent_tools",
    "seed_caution_drafter_agent",
    "seed_run_debrief_agent",
    "wire_agent",
]
