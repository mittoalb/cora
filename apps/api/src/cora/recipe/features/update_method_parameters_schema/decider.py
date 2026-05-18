"""Pure decider for the `UpdateMethodParametersSchema` command.

Phase 6g-a. Mostly delegates to `validate_parameters_schema` for
well-formedness; the only domain-level guard is "Method must exist".
Schema can be updated in any lifecycle status (Defined / Versioned /
Deprecated) so no source-state check.

## Idempotency: no-op on unchanged

If the proposed parameters_schema is structurally equal to the
current one (including both being None), no event is emitted. This
avoids audit-log noise from operators re-submitting the same schema;
per-attestation re-emission is meaningful for content versioning
(see version_method's "strict-not-idempotent-with-exception"
rationale) but not for schema declarations, where the value IS the
audit trail and identical re-submission carries no new information.
Mirrors `update_family_settings_schema` (Equipment 5g-a) decider stance.

Invariants:
  - State must not be None -> MethodNotFoundError
  - parameters_schema (if non-None) must be a valid in-subset
    JSON Schema -> InvalidMethodParametersSchemaError
  - If proposed == current, return [] (no event emitted)
"""

from datetime import datetime

from cora.recipe.aggregates.method import (
    Method,
    MethodNotFoundError,
    MethodParametersSchemaUpdated,
    validate_parameters_schema,
)
from cora.recipe.features.update_method_parameters_schema.command import (
    UpdateMethodParametersSchema,
)


def decide(
    state: Method | None,
    command: UpdateMethodParametersSchema,
    *,
    now: datetime,
) -> list[MethodParametersSchemaUpdated]:
    """Decide the events produced by updating a method's parameters_schema."""
    if state is None:
        raise MethodNotFoundError(command.method_id)
    if command.parameters_schema is not None:
        validate_parameters_schema(command.parameters_schema)
    if command.parameters_schema == state.parameters_schema:
        return []
    return [
        MethodParametersSchemaUpdated(
            method_id=state.id,
            parameters_schema=command.parameters_schema,
            occurred_at=now,
        )
    ]
