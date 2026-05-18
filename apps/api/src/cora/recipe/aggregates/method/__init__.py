"""Method aggregate: state, status enum, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.recipe.features.<verb>_method/` and import from here for
state and event types.
"""

from cora.recipe.aggregates.method.events import (
    MethodDefined,
    MethodDeprecated,
    MethodEvent,
    MethodParametersSchemaUpdated,
    MethodVersioned,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.recipe.aggregates.method.evolver import evolve, fold
from cora.recipe.aggregates.method.parameters_validation import (
    InvalidMethodParametersSchemaError,
    validate_parameters_schema,
)
from cora.recipe.aggregates.method.read import load_method
from cora.recipe.aggregates.method.state import (
    METHOD_NAME_MAX_LENGTH,
    METHOD_NEEDS_SUPPLY_KIND_MAX_LENGTH,
    METHOD_VERSION_TAG_MAX_LENGTH,
    InvalidMethodNameError,
    InvalidMethodNeededSuppliesError,
    InvalidMethodVersionTagError,
    Method,
    MethodAlreadyExistsError,
    MethodCannotDeprecateError,
    MethodCannotVersionError,
    MethodName,
    MethodNotFoundError,
    MethodParametersNotSubsetError,
    MethodStatus,
)

__all__ = [
    "METHOD_NAME_MAX_LENGTH",
    "METHOD_NEEDS_SUPPLY_KIND_MAX_LENGTH",
    "METHOD_VERSION_TAG_MAX_LENGTH",
    "InvalidMethodNameError",
    "InvalidMethodNeededSuppliesError",
    "InvalidMethodParametersSchemaError",
    "InvalidMethodVersionTagError",
    "Method",
    "MethodAlreadyExistsError",
    "MethodCannotDeprecateError",
    "MethodCannotVersionError",
    "MethodDefined",
    "MethodDeprecated",
    "MethodEvent",
    "MethodName",
    "MethodNotFoundError",
    "MethodParametersNotSubsetError",
    "MethodParametersSchemaUpdated",
    "MethodStatus",
    "MethodVersioned",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_method",
    "to_payload",
    "validate_parameters_schema",
]
