"""The `ListCautions` query: intent dataclass for keyset-paginated
list of cautions from the `proj_caution_active` projection.

Eight optional filters (target_kind / target_id / category / severity /
min_severity / status / tag / author_actor_id). The default behavior
(no status passed) returns Active cautions only, matching the design
memo's "default `status=Active` if omitted, `status=all` to include
Superseded+Retired".

`min_severity` (Notice / Caution / Warning) returns cautions whose
severity is >= the threshold. Mapped to an integer ordinal in the
handler before binding so the SQL CASE expression can do a numeric
comparison.

`tag` filters cautions whose `tags` array contains the given value
(GIN index on the projection).

Cursor encodes `(registered_at, caution_id)`. `registered_at` is set
once at CautionRegistered (immutable), so it's a stable keyset key.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

CautionTargetKindFilter = Literal["Asset", "Procedure"]

CautionCategoryFilter = Literal[
    "Wear",
    "Calibration",
    "Wiring",
    "OperationalWindow",
    "InterlockQuirk",
    "ProcedureGotcha",
]

CautionSeverityFilter = Literal["Notice", "Caution", "Warning"]

# Status carries the "all" sentinel in addition to the three real statuses.
# Handler default (None -> Active) and "all" (no filter) are mapped in
# Python before binding.
CautionStatusFilter = Literal[
    "Active",
    "Superseded",
    "Retired",
    "all",
]


@dataclass(frozen=True)
class ListCautions:
    """Read a keyset-paginated page of cautions from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    target_kind: CautionTargetKindFilter | None = None
    """Optional target-kind filter (Asset / Procedure)."""

    target_id: UUID | None = None
    """Optional target-id filter (typically used with target_kind)."""

    category: CautionCategoryFilter | None = None
    """Optional category filter (one of the 6 CautionCategory values)."""

    severity: CautionSeverityFilter | None = None
    """Optional exact-severity filter (Notice / Caution / Warning)."""

    min_severity: CautionSeverityFilter | None = None
    """Optional threshold filter; returns severity >= threshold."""

    status: CautionStatusFilter | None = None
    """Optional status filter; None defaults to 'Active' in the handler.

    Pass 'all' to disable status filtering (returns Active + Superseded
    + Retired); pass an exact value to filter to that status only.
    """

    tag: str | None = None
    """Optional tag filter; matches any caution whose `tags` array contains this value."""

    author_actor_id: UUID | None = None
    """Optional author filter (operator dashboard 'cautions I authored')."""
