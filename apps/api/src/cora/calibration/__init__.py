"""Calibration BC (Phase 12).

Empirical instrument-value records keyed by `(subsystem_or_asset_id,
CalibrationQuantity, operating_point)` with append-only revision
history. Sibling to Safety (11a) + Caution (11b) per
[[project_calibration_design]] Stage 1 lock.

The Calibration aggregate captures what the alignment Procedure
*measured* (Measured source), what numerical methods *computed* from
acquired Datasets (Computed source), and what operators *asserted*
directly (Asserted source). Run.pinned_calibrations records what was
live at scan start (AsShot anchor per DNG precedent); reconstructed
Dataset.calibrations_used may cite later refined revisions (Current
vs AsShot pattern).

See `docs/projects/2-bm/calibration.md` (when written) for the
operator-facing inventory; the design memo at
`project_calibration_design.md` is the authoritative source for the
domain model.
"""

from cora.calibration._projections import register_calibration_projections
from cora.calibration.routes import register_calibration_routes
from cora.calibration.tools import register_calibration_tools
from cora.calibration.wire import CalibrationHandlers, wire_calibration

__all__ = [
    "CalibrationHandlers",
    "register_calibration_projections",
    "register_calibration_routes",
    "register_calibration_tools",
    "wire_calibration",
]
