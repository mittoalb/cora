"""Conduit aggregate: state, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.trust.features.<verb>_conduit/` and import from here for state
and event types.

Logbook-lifecycle infrastructure: `logbooks` (dict mapping kind →
currently-open logbook id) on the aggregate state,
`ConduitLogbookOpened` / `ConduitLogbookClosed` events on the main
stream, and the `verdicts` logbook kind constant. Per-decision
authz audit entries live in the sibling `entries.py` module
(separate from the aggregate event-store path).
"""

from cora.trust.aggregates.conduit.events import (
    ConduitDefined,
    ConduitEvent,
    ConduitLogbookClosed,
    ConduitLogbookOpened,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.trust.aggregates.conduit.evolver import evolve, fold
from cora.trust.aggregates.conduit.read import load_conduit
from cora.trust.aggregates.conduit.state import (
    CONDUIT_NAME_MAX_LENGTH,
    LOGBOOK_KIND_VERDICT,
    Conduit,
    ConduitAlreadyExistsError,
    ConduitLogbookAlreadyOpenError,
    ConduitLogbookNotOpenError,
    ConduitName,
    InvalidConduitNameError,
)

__all__ = [
    "CONDUIT_NAME_MAX_LENGTH",
    "LOGBOOK_KIND_VERDICT",
    "Conduit",
    "ConduitAlreadyExistsError",
    "ConduitDefined",
    "ConduitEvent",
    "ConduitLogbookAlreadyOpenError",
    "ConduitLogbookClosed",
    "ConduitLogbookNotOpenError",
    "ConduitLogbookOpened",
    "ConduitName",
    "InvalidConduitNameError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_conduit",
    "to_payload",
]
