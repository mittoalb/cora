"""Agent BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_agent_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry. Agent BC's first
projection ships in audit-2026-05-20 Iter C-1 per the Path C lock
(state stays decider-minimal; lifecycle timestamps live on the
projection — mirrors Method/Plan/Practice/Family/Capability).
"""

from cora.agent.projections import AgentSummaryProjection
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry


def register_agent_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Agent-owned projection on the worker registry."""
    _ = deps
    registry.register(AgentSummaryProjection())


__all__ = ["register_agent_projections"]
