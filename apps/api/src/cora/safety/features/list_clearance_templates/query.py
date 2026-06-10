"""The `ListClearanceTemplates` query: intent dataclass for keyset-paginated
list of clearance templates from the projection.

Four optional filters: facility_code (cross-deployment convergent slug;
exact match), status (one of the ClearanceTemplateStatus values),
code (free-form display text; exact match). All correspond to real ops
queries: "show me APS form templates", "show me active templates",
"show me ESAF templates across all facilities".

No default exclusion of Withdrawn rows: matches the cross-BC convention
from Asset (`AssetLifecycleFilter` includes `Decommissioned`) and
Supply (`SupplyStatusFilter` includes `Decommissioned`). An unfiltered
`list_clearance_templates` returns every status; callers who want
only-active set `status=Active` explicitly. Callers who want to audit
withdrawn templates set `status=Withdrawn`.

`ClearanceTemplateStatusFilter` is locked at the full enum width:
forward-compat motivation: when later transition slices land, no
Pydantic schema change required; OpenAPI documents the full FSM up
front for ops engineers.

Cursor encodes (defined_at, template_id): `defined_at` is set once at
ClearanceTemplateDefined (immutable), so it's a stable keyset key.
Mirrors `list_families` cursor exactly.
"""

from dataclasses import dataclass
from typing import Literal

ClearanceTemplateStatusFilter = Literal[
    "Draft",
    "Active",
    "Deprecated",
    "Withdrawn",
]


@dataclass(frozen=True)
class ListClearanceTemplates:
    """Read a keyset-paginated page of clearance templates from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    facility_code: str | None = None
    """Optional facility-code filter (exact match against the cross-
    deployment convergent slug, for example `'aps'`, `'maxiv'`)."""

    status: ClearanceTemplateStatusFilter | None = None
    """Optional status filter (one of the four ClearanceTemplateStatus values)."""

    code: str | None = None
    """Optional code filter (free-form, exact match)."""
