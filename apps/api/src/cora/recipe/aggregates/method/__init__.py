"""Method aggregate: state, status enum, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.recipe.features.<verb>_method/` and import from here for
state and event types.
"""

from cora.recipe.aggregates.method.events import (
    MethodDefined,
    MethodEvent,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.recipe.aggregates.method.evolver import evolve, fold
from cora.recipe.aggregates.method.read import load_method
from cora.recipe.aggregates.method.state import (
    METHOD_NAME_MAX_LENGTH,
    InvalidMethodNameError,
    Method,
    MethodAlreadyExistsError,
    MethodName,
    MethodNotFoundError,
    MethodStatus,
)

__all__ = [
    "METHOD_NAME_MAX_LENGTH",
    "InvalidMethodNameError",
    "Method",
    "MethodAlreadyExistsError",
    "MethodDefined",
    "MethodEvent",
    "MethodName",
    "MethodNotFoundError",
    "MethodStatus",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_method",
    "to_payload",
]
