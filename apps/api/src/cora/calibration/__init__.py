"""Calibration BC.

Empirical instrument-value records keyed by `(target_id,
CalibrationQuantity, operating_point)` with append-only revision
history. Sibling to Safety + Caution per [[project_calibration_design]].

The Calibration aggregate captures what the alignment Procedure
*measured* (Measured source), what numerical methods *computed* from
acquired Datasets (Computed source), and what operators *asserted*
directly (Asserted source). Run.pinned_calibration_ids records what was
live at scan start (AsShot anchor per DNG precedent); reconstructed
Dataset.used_calibration_ids may cite later refined revisions (per the
Calibration BC's revision-cited atomic-ID model — the Dataset's set
is its own list of revision IDs, not an attribute-overlay on top of
the Run's set; see [[project_calibration_design]] anti-hook #3 +
#13).

See `docs/projects/2-bm/calibration.md` (when written) for the
operator-facing inventory; the design memo at
`project_calibration_design.md` is the authoritative source for the
domain model.
"""

from cora.calibration._projections import register_calibration_projections
from cora.calibration.errors import UnauthorizedError
from cora.calibration.routes import register_calibration_routes
from cora.calibration.tools import register_calibration_tools
from cora.calibration.wire import CalibrationHandlers, wire_calibration

__all__ = [
    "CalibrationHandlers",
    "UnauthorizedError",
    "register_calibration_projections",
    "register_calibration_routes",
    "register_calibration_tools",
    "wire_calibration",
]
