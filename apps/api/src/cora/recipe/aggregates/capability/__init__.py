"""Capability aggregate: state, status, executor-shape, errors, events, evolver, read.

Phase 6k. The universal declarative template at the operations
layer per [[project-capability-aggregate-design]]; sits above
heterogeneous executor shapes (Method-chain for science, Procedure
for ceremony) per the universal-template-above-heterogeneous-
executors pattern locked in [[project-capability-research]]
Round 3.

Vertical slices that operate on this aggregate live under
`cora.recipe.features.<verb>_capability/` and import from here for
state, events, and error types.
"""

from cora.recipe.aggregates.capability.events import (
    CapabilityDefined,
    CapabilityDeprecated,
    CapabilityEvent,
    CapabilityVersioned,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.recipe.aggregates.capability.evolver import evolve, fold
from cora.recipe.aggregates.capability.executor_shape import ExecutorShape
from cora.recipe.aggregates.capability.parameter_schema_validation import (
    InvalidCapabilityParameterSchemaError,
    validate_capability_parameter_schema,
)
from cora.recipe.aggregates.capability.read import load_capability
from cora.recipe.aggregates.capability.state import (
    CAPABILITY_CODE_MAX_LENGTH,
    CAPABILITY_CODE_NAMESPACE_PREFIX,
    CAPABILITY_DESCRIPTION_MAX_LENGTH,
    CAPABILITY_NAME_MAX_LENGTH,
    CAPABILITY_VERSION_TAG_MAX_LENGTH,
    Capability,
    CapabilityAlreadyExistsError,
    CapabilityCannotDeprecateError,
    CapabilityCannotVersionError,
    CapabilityCode,
    CapabilityName,
    CapabilityNotFoundError,
    CapabilityStatus,
    InvalidCapabilityCodeError,
    InvalidCapabilityDescriptionError,
    InvalidCapabilityNameError,
    InvalidCapabilityVersionTagError,
    InvalidExecutorShapesError,
    validate_capability_description,
    validate_executor_shapes,
)

__all__ = [
    "CAPABILITY_CODE_MAX_LENGTH",
    "CAPABILITY_CODE_NAMESPACE_PREFIX",
    "CAPABILITY_DESCRIPTION_MAX_LENGTH",
    "CAPABILITY_NAME_MAX_LENGTH",
    "CAPABILITY_VERSION_TAG_MAX_LENGTH",
    "Capability",
    "CapabilityAlreadyExistsError",
    "CapabilityCannotDeprecateError",
    "CapabilityCannotVersionError",
    "CapabilityCode",
    "CapabilityDefined",
    "CapabilityDeprecated",
    "CapabilityEvent",
    "CapabilityName",
    "CapabilityNotFoundError",
    "CapabilityStatus",
    "CapabilityVersioned",
    "ExecutorShape",
    "InvalidCapabilityCodeError",
    "InvalidCapabilityDescriptionError",
    "InvalidCapabilityNameError",
    "InvalidCapabilityParameterSchemaError",
    "InvalidCapabilityVersionTagError",
    "InvalidExecutorShapesError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_capability",
    "to_payload",
    "validate_capability_description",
    "validate_capability_parameter_schema",
    "validate_executor_shapes",
]
