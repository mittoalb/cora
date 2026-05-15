"""Operation BC projections.

Today: just `ProcedureSummaryProjection` (Phase 10c-c iter 2). Future
projections (per-step rollup, per-Run aggregation, etc.) land here as
sibling modules.
"""

from cora.operation.projections.procedure import ProcedureSummaryProjection

__all__ = ["ProcedureSummaryProjection"]
