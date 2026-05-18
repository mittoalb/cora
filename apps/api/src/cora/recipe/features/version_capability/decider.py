"""Pure decider for the `VersionCapability` command.

Multi-source-state transition: `Defined | Versioned -> Versioned`.
Both Defined (first revision) and Versioned (subsequent revisions)
are valid sources; only Deprecated is rejected.

Re-attestation: calling version_capability with the same version_tag
+ same declarative contract twice both succeed, producing two
`CapabilityVersioned` events. Re-attestation is a legitimate audit
moment ("the operator confirmed v2 again on date X"); the multi-
source Versioned → Versioned transition permits the operation
structurally. Same precedent as version_family.

Invariants:
  - State must not be None -> CapabilityNotFoundError
  - command.version_tag must be 1-50 chars after trimming
    -> InvalidCapabilityVersionTagError
  - command.description (when supplied) must be 0-2000 chars
    -> InvalidCapabilityDescriptionError
  - command.executor_shapes must be non-empty
    -> InvalidExecutorShapesError
  - command.parameter_schema (when supplied) must be a valid
    in-subset JSON Schema -> InvalidCapabilityParameterSchemaError
  - State.status must be in {Defined, Versioned}
    -> CapabilityCannotVersionError(current_status=...)
"""

from datetime import datetime

from cora.recipe.aggregates.capability import (
    CAPABILITY_VERSION_TAG_MAX_LENGTH,
    Capability,
    CapabilityCannotVersionError,
    CapabilityNotFoundError,
    CapabilityStatus,
    CapabilityVersioned,
    InvalidCapabilityVersionTagError,
    validate_capability_description,
    validate_capability_parameter_schema,
    validate_executor_shapes,
)
from cora.recipe.features.version_capability.command import VersionCapability

_VERSIONABLE_STATUSES: tuple[CapabilityStatus, ...] = (
    CapabilityStatus.DEFINED,
    CapabilityStatus.VERSIONED,
)


def decide(
    state: Capability | None,
    command: VersionCapability,
    *,
    now: datetime,
) -> list[CapabilityVersioned]:
    """Decide the events produced by versioning an existing Capability."""
    if state is None:
        raise CapabilityNotFoundError(command.capability_id)
    trimmed = command.version_tag.strip()
    if not trimmed or len(trimmed) > CAPABILITY_VERSION_TAG_MAX_LENGTH:
        raise InvalidCapabilityVersionTagError(command.version_tag)
    description = validate_capability_description(command.description)
    executor_shapes = validate_executor_shapes(command.executor_shapes)
    if command.parameter_schema is not None:
        validate_capability_parameter_schema(command.parameter_schema)
    if state.status not in _VERSIONABLE_STATUSES:
        raise CapabilityCannotVersionError(state.id, current_status=state.status)
    return [
        CapabilityVersioned(
            capability_id=state.id,
            version_tag=trimmed,
            description=description,
            required_affordances=command.required_affordances,
            executor_shapes=executor_shapes,
            parameter_schema=command.parameter_schema,
            occurred_at=now,
        )
    ]
