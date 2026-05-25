"""The `ListCalibrations` query — keyset-paginated list from
`proj_calibration_summary`.

Five optional filters in canonical form:

  - `target_id` (single-value, exact-match): scope to a
    single Asset/subsystem's calibrations.
  - `quantity` (CalibrationQuantity value-string): scope to one
    quantity (for example, all rotation_center calibrations).
  - `latest_revision_statuses` (list of acceptable status values;
    None = no filter): filter by the most recent revision's status.
  - `latest_revision_source_kinds` (list of acceptable source-kind
    strings; None = no filter): filter by the most recent revision's
    source kind (measured / computed / asserted).
  - Pagination via `cursor` + `limit`.

User-facing UX (single-value `status` shortcut, `?source_kind=all`
sentinel) lives at the route boundary, NOT in this dataclass.

Cursor encodes `(defined_at, calibration_id)`. `defined_at` is set
once at genesis (immutable), so it's a stable keyset key.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

CalibrationStatusFilter = Literal["Provisional", "Verified"]
CalibrationSourceKindFilter = Literal["measured", "computed", "asserted"]


@dataclass(frozen=True)
class ListCalibrations:
    """Read a keyset-paginated page of calibrations from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    target_id: UUID | None = None
    """Optional scope filter: only calibrations OF this Asset/subsystem."""

    quantity: str | None = None
    """Optional quantity filter (CalibrationQuantity value-string)."""

    latest_revision_statuses: list[CalibrationStatusFilter] | None = None
    """Optional set of acceptable latest-revision status values; None
    or [] treated as no filter by the factory."""

    latest_revision_source_kinds: list[CalibrationSourceKindFilter] | None = None
    """Optional set of acceptable latest-revision source-kind values
    (string-form: 'measured' / 'computed' / 'asserted'); None or []
    treated as no filter."""
