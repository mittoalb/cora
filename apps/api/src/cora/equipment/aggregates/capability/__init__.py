"""Capability aggregate: state, status enum, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.equipment.features.<verb>_capability/` and import from here for
state and event types.
"""

from cora.equipment.aggregates.capability.events import (
    CapabilityDefined,
    CapabilityEvent,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.equipment.aggregates.capability.evolver import evolve, fold
from cora.equipment.aggregates.capability.read import load_capability
from cora.equipment.aggregates.capability.state import (
    CAPABILITY_NAME_MAX_LENGTH,
    Capability,
    CapabilityAlreadyExistsError,
    CapabilityName,
    CapabilityNotFoundError,
    CapabilityStatus,
    InvalidCapabilityNameError,
)

__all__ = [
    "CAPABILITY_NAME_MAX_LENGTH",
    "Capability",
    "CapabilityAlreadyExistsError",
    "CapabilityDefined",
    "CapabilityEvent",
    "CapabilityName",
    "CapabilityNotFoundError",
    "CapabilityStatus",
    "InvalidCapabilityNameError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_capability",
    "to_payload",
]
