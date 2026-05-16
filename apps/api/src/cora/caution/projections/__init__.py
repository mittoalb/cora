"""Caution BC projections.

Single-aggregate BC, single projection: CautionSummaryProjection backs
`GET /cautions` (list) and complements `GET /cautions/{id}` (which
still uses fold-on-read for canonical state).

Add a new projection by creating a new module here + re-exporting its
class + adding it to `register_caution_projections`.
"""

from cora.caution.projections.caution import CautionSummaryProjection

__all__ = ["CautionSummaryProjection"]
