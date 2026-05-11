"""Conduit aggregate: state, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.trust.features.<verb>_conduit/` and import from here for state
and event types.

Phase 6f-5a adds channel-lifecycle infrastructure: `channels`
(dict mapping kind → currently-open channel id) on the aggregate
state, `ConduitChannelOpened` / `ConduitChannelClosed` events on
the main stream, and the `traversals` channel kind constant.
Per-decision authz audit observations live in the sibling
`observations.py` module (separate from the aggregate event-store
path).
"""

from cora.trust.aggregates.conduit.events import (
    ConduitChannelClosed,
    ConduitChannelOpened,
    ConduitDefined,
    ConduitEvent,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.trust.aggregates.conduit.evolver import evolve, fold
from cora.trust.aggregates.conduit.read import load_conduit
from cora.trust.aggregates.conduit.state import (
    CHANNEL_KIND_TRAVERSALS,
    CONDUIT_NAME_MAX_LENGTH,
    Conduit,
    ConduitAlreadyExistsError,
    ConduitChannelAlreadyOpenError,
    ConduitChannelNotOpenError,
    ConduitName,
    InvalidConduitNameError,
)

__all__ = [
    "CHANNEL_KIND_TRAVERSALS",
    "CONDUIT_NAME_MAX_LENGTH",
    "Conduit",
    "ConduitAlreadyExistsError",
    "ConduitChannelAlreadyOpenError",
    "ConduitChannelClosed",
    "ConduitChannelNotOpenError",
    "ConduitChannelOpened",
    "ConduitDefined",
    "ConduitEvent",
    "ConduitName",
    "InvalidConduitNameError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_conduit",
    "to_payload",
]
