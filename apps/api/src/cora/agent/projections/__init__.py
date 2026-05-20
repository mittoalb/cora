"""Agent BC's projection modules.

Agent BC ships its first projection in audit-2026-05-20 Iter C-1
per the Path C lock: state stays decider-minimal; lifecycle
timestamps live on the projection. Mirrors the per-BC convention
where each `cora.<bc>.projections.<aggregate>` module owns a single
`*SummaryProjection` class registered via `cora.<bc>._projections`.
"""

from cora.agent.projections.agent import AgentSummaryProjection

__all__ = ["AgentSummaryProjection"]
