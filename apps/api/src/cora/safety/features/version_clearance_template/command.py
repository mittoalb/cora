"""The `VersionClearanceTemplate` command -- intent dataclass for this slice.

Records a new version of an Active ClearanceTemplate, chaining to a parent
template via `supersedes_template_id`. The handler validates the parent via
`ClearanceTemplateLookup` and the decider enforces same-facility chaining
plus the `new_version == state.version + 1` invariant.

Versioning is additive within the Active status (no FSM transition); see
[[project_slice9_design]] L4. The parent reference is required because
versioning is meaningless without a forebear, and capturing the operator's
asserted parent in the command keeps the chain auditable end-to-end.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class VersionClearanceTemplate:
    """Record a new version of an Active clearance template."""

    template_id: UUID
    new_version: int
    supersedes_template_id: UUID
