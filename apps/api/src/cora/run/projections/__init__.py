"""Run BC projections.

Single-aggregate BC; one projection today (RunSummaryProjection).
Add a new projection by creating a new module here + re-exporting
its class + adding it to `register_run_projections`.
"""

from cora.run.projections.summary import RunSummaryProjection

__all__ = ["RunSummaryProjection"]
