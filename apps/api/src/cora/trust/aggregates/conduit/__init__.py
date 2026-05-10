"""Conduit aggregate: state, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.trust.features.<verb>_conduit/` and import from here for state
and event types.
"""

from cora.trust.aggregates.conduit.events import (
    ConduitDefined,
    ConduitEvent,
    event_type_name,
    from_stored,
    to_new_event,
    to_payload,
)
from cora.trust.aggregates.conduit.evolver import evolve, fold
from cora.trust.aggregates.conduit.read import load_conduit
from cora.trust.aggregates.conduit.state import (
    CONDUIT_NAME_MAX_LENGTH,
    Conduit,
    ConduitAlreadyExistsError,
    ConduitName,
    InvalidConduitNameError,
)

__all__ = [
    "CONDUIT_NAME_MAX_LENGTH",
    "Conduit",
    "ConduitAlreadyExistsError",
    "ConduitDefined",
    "ConduitEvent",
    "ConduitName",
    "InvalidConduitNameError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_conduit",
    "to_new_event",
    "to_payload",
]
