"""Pure decider for the `UpdateFamilySettingsSchema` command.

Phase 5g-a. Mostly delegates to `validate_settings_schema` for
well-formedness; the only domain-level guard is "Family must
exist". Schema can be updated in any lifecycle status (Defined /
Versioned / Deprecated) so no source-state check.

## Idempotency: no-op on unchanged

If the proposed settings_schema is structurally equal to the
current one (including both being None), no event is emitted.
This avoids audit-log noise from operators re-submitting the same
schema; per-attestation re-emission is meaningful for content
versioning (see version_family's
"strict-not-idempotent-with-exception" rationale) but not for
schema declarations, where the value IS the audit trail and
identical re-submission carries no new information.

Invariants:
  - State must not be None -> FamilyNotFoundError
  - settings_schema (if non-None) must be a valid in-subset
    JSON Schema -> InvalidFamilySettingsSchemaError
  - If proposed == current, return [] (no event emitted)
"""

from datetime import datetime

from cora.equipment.aggregates.family import (
    Family,
    FamilyNotFoundError,
    FamilySettingsSchemaUpdated,
    validate_settings_schema,
)
from cora.equipment.features.update_family_settings_schema.command import (
    UpdateFamilySettingsSchema,
)


def decide(
    state: Family | None,
    command: UpdateFamilySettingsSchema,
    *,
    now: datetime,
) -> list[FamilySettingsSchemaUpdated]:
    """Decide the events produced by updating a family's schema."""
    if state is None:
        raise FamilyNotFoundError(command.family_id)
    if command.settings_schema is not None:
        validate_settings_schema(command.settings_schema)
    if command.settings_schema == state.settings_schema:
        return []
    return [
        FamilySettingsSchemaUpdated(
            family_id=state.id,
            settings_schema=command.settings_schema,
            occurred_at=now,
        )
    ]
