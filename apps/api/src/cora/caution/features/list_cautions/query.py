"""The `ListCautions` query: intent dataclass for keyset-paginated
list of cautions from the `proj_caution_summary` projection.

Seven optional filters in canonical form:

  - target_kind / target_id / category / tag / authored_by
    (single-value, exact-match)
  - severities (list of acceptable severity values; None == no filter)
  - statuses (list of acceptable status values; None == no filter)

User-facing UX (`min_severity` ladder, status default-to-Active,
`status='all'` opt-in) lives at the route/MCP-tool boundary, NOT
in this dataclass. The route translates user input into the
canonical list-typed `severities` / `statuses` fields before
constructing the query.

The query dataclass is the canonical internal contract: anything
constructing `ListCautions(...)` directly (tests, internal code)
sees a uniform "None means no filter" semantic for every field,
matching every other list-query slice in the codebase.

Cursor encodes `(registered_at, caution_id)`. `registered_at` is
set once at CautionRegistered (immutable), so it's a stable keyset
key.
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

CautionStatusFilter = Literal["Active", "Superseded", "Retired"]


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

    severities: list[CautionSeverityFilter] | None = None
    """Optional set of acceptable severity values; None == no filter,
    empty list also treated as no filter by the factory.

    Route translates user-facing `severity` (singleton) and
    `min_severity` (Notice<Caution<Warning ladder) into a single
    list, returning 422 on conflicting inputs."""

    statuses: list[CautionStatusFilter] | None = None
    """Optional set of acceptable status values; None == no filter,
    empty list also treated as no filter by the factory.

    Route applies the operator-UX default ([Active]) when the
    request omits the status param; the user opts into the full
    history by passing every status explicitly OR by passing the
    route-level `?status=all` sentinel which the route translates
    to None here."""

    tag: str | None = None
    """Optional tag filter; matches any caution whose `tags` array contains this value."""

    authored_by: UUID | None = None
    """Optional author filter (operator dashboard 'cautions I authored')."""
