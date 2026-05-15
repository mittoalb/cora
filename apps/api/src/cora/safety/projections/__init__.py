"""Read-side projections owned by the Safety BC.

11a-b: `ClearanceSummaryProjection` folds the Clearance aggregate's
lifecycle events into `proj_safety_clearance_summary`.
"""

from cora.safety.projections.clearance import ClearanceSummaryProjection

__all__ = ["ClearanceSummaryProjection"]
