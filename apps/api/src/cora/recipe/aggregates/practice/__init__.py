"""Practice aggregate: state, status enum, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.recipe.features.<verb>_practice/` and import from here for
state and event types.
"""

from cora.recipe.aggregates.practice.events import (
    PracticeDefined,
    PracticeDeprecated,
    PracticeEvent,
    PracticeVersioned,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.recipe.aggregates.practice.evolver import evolve, fold
from cora.recipe.aggregates.practice.read import load_practice
from cora.recipe.aggregates.practice.state import (
    PRACTICE_NAME_MAX_LENGTH,
    PRACTICE_VERSION_TAG_MAX_LENGTH,
    InvalidPracticeNameError,
    InvalidPracticeVersionTagError,
    Practice,
    PracticeAlreadyExistsError,
    PracticeCannotDeprecateError,
    PracticeCannotVersionError,
    PracticeName,
    PracticeNotFoundError,
    PracticeStatus,
)

__all__ = [
    "PRACTICE_NAME_MAX_LENGTH",
    "PRACTICE_VERSION_TAG_MAX_LENGTH",
    "InvalidPracticeNameError",
    "InvalidPracticeVersionTagError",
    "Practice",
    "PracticeAlreadyExistsError",
    "PracticeCannotDeprecateError",
    "PracticeCannotVersionError",
    "PracticeDefined",
    "PracticeDeprecated",
    "PracticeEvent",
    "PracticeName",
    "PracticeNotFoundError",
    "PracticeStatus",
    "PracticeVersioned",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_practice",
    "to_payload",
]
