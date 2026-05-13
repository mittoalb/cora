"""Pure decider for the `UpdateCapabilitySchema` command.

Phase 5g-a. Mostly delegates to `validate_settings_schema` for
well-formedness; the only domain-level guard is "Capability must
exist". Schema can be updated in any lifecycle status (Defined /
Versioned / Deprecated) so no source-state check.

## Idempotency: no-op on unchanged

If the proposed settings_schema is structurally equal to the
current one (including both being None), no event is emitted.
This avoids audit-log noise from operators re-submitting the same
schema; per-attestation re-emission is meaningful for content
versioning (see version_capability's
"strict-not-idempotent-with-exception" rationale) but not for
schema declarations, where the value IS the audit trail and
identical re-submission carries no new information.

Invariants:
  - State must not be None -> CapabilityNotFoundError
  - settings_schema (if non-None) must be a valid in-subset
    JSON Schema -> InvalidCapabilitySchemaError
  - If proposed == current, return [] (no event emitted)
"""

from datetime import datetime

from cora.equipment.aggregates.capability import (
    Capability,
    CapabilityNotFoundError,
    CapabilitySchemaUpdated,
    validate_settings_schema,
)
from cora.equipment.features.update_capability_schema.command import (
    UpdateCapabilitySchema,
)


def decide(
    state: Capability | None,
    command: UpdateCapabilitySchema,
    *,
    now: datetime,
) -> list[CapabilitySchemaUpdated]:
    """Decide the events produced by updating a capability's schema."""
    if state is None:
        raise CapabilityNotFoundError(command.capability_id)
    if command.settings_schema is not None:
        validate_settings_schema(command.settings_schema)
    if command.settings_schema == state.settings_schema:
        return []
    return [
        CapabilitySchemaUpdated(
            capability_id=state.id,
            settings_schema=command.settings_schema,
            occurred_at=now,
        )
    ]
