"""Agent BC's projection modules.

Agent BC ships its first projection per the Path C lock: state
stays decider-minimal; lifecycle timestamps live on the projection.
Mirrors the per-BC convention where each
`cora.<bc>.projections.<aggregate>` module owns a single
`*SummaryProjection` class registered via `cora.<bc>._projections`.
"""

from cora.agent.projections.agent import AgentSummaryProjection

__all__ = ["AgentSummaryProjection"]
