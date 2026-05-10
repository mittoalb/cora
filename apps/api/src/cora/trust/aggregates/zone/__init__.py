"""Zone aggregate: state, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.trust.features.<verb>_zone/` and import from here for state and
event types.
"""

from cora.trust.aggregates.zone.events import (
    ZoneDefined,
    ZoneEvent,
    event_type_name,
    from_stored,
    to_new_event,
    to_payload,
)
from cora.trust.aggregates.zone.evolver import evolve, fold
from cora.trust.aggregates.zone.read import load_zone
from cora.trust.aggregates.zone.state import (
    ZONE_NAME_MAX_LENGTH,
    InvalidZoneNameError,
    Zone,
    ZoneAlreadyExistsError,
    ZoneName,
)

__all__ = [
    "ZONE_NAME_MAX_LENGTH",
    "InvalidZoneNameError",
    "Zone",
    "ZoneAlreadyExistsError",
    "ZoneDefined",
    "ZoneEvent",
    "ZoneName",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_zone",
    "to_new_event",
    "to_payload",
]
