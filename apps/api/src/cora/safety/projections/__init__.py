"""Read-side projections owned by the Safety BC.

Projections:

- `ClearanceSummaryProjection` (11a-b): folds Clearance lifecycle events
  into `proj_safety_clearance_summary`, backing `GET /clearances` (list) and
  complementing `GET /clearances/{id}` (fold-on-read).
- `ClearanceTemplateSummaryProjection` (9A): folds ClearanceTemplate genesis
  events into `proj_safety_clearance_template_summary`, backing
  `GET /clearance_templates` (list) and complementing
  `GET /clearance_templates/{id}` (fold-on-read).

Add a new projection by creating a new module here, re-exporting its class,
and adding it to `register_safety_projections` in `_projections.py`.
"""

from cora.safety.projections.clearance import ClearanceSummaryProjection
from cora.safety.projections.clearance_template import ClearanceTemplateSummaryProjection

__all__ = ["ClearanceSummaryProjection", "ClearanceTemplateSummaryProjection"]
