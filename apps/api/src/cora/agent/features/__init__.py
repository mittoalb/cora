"""Vertical slices for the Agent BC.

Phase 8f-a ships:
  - `define_agent`    (cross-BC atomic via EventStore.append_streams;
                       writes ActorRegistered(kind="agent") + AgentDefined;
                       create-style; idempotency-wrapped)
  - `version_agent`   (Defined -> Versioned; single-stream)
  - `deprecate_agent` (Defined | Versioned -> Deprecated; single-stream)
  - `get_agent`       (read; fold-on-read)

No projection / list_agents slice at 8f-a (deferred until per-kind
active-agent queries surface; see [[project_agent_bc_design]] watch
items).
"""

from cora.agent.features import (
    define_agent,
    deprecate_agent,
    get_agent,
    version_agent,
)

__all__ = [
    "define_agent",
    "deprecate_agent",
    "get_agent",
    "version_agent",
]
