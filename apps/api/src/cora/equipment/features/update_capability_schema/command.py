"""The `UpdateCapabilitySchema` command — intent dataclass for this slice.

Phase 5g-a. Operators set, replace, or clear the JSON Schema
declaring the shape of `Asset.settings` keys this Capability owns.
Independent of the Defined / Versioned / Deprecated content
lifecycle: schema iteration is its own audit stream.

`settings_schema=None` is a valid intent (clear the schema). The
decider validates well-formedness via
`schema_validation.validate_settings_schema` before emitting
`CapabilitySchemaUpdated`. See [[project_capability_settings_schema]]
memory for the locked subset + validation policy.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class UpdateCapabilitySchema:
    """Set / replace / clear a Capability's settings_schema."""

    capability_id: UUID
    settings_schema: dict[str, Any] | None
