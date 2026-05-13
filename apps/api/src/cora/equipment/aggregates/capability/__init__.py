"""Capability aggregate: state, status enum, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.equipment.features.<verb>_capability/` and import from here for
state and event types.
"""

from cora.equipment.aggregates.capability.events import (
    CapabilityDefined,
    CapabilityDeprecated,
    CapabilityEvent,
    CapabilitySchemaUpdated,
    CapabilityVersioned,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.equipment.aggregates.capability.evolver import evolve, fold
from cora.equipment.aggregates.capability.read import load_capability
from cora.equipment.aggregates.capability.schema_validation import (
    InvalidCapabilitySchemaError,
    validate_settings_schema,
)
from cora.equipment.aggregates.capability.state import (
    CAPABILITY_NAME_MAX_LENGTH,
    CAPABILITY_VERSION_TAG_MAX_LENGTH,
    Capability,
    CapabilityAlreadyExistsError,
    CapabilityCannotDeprecateError,
    CapabilityCannotVersionError,
    CapabilityName,
    CapabilityNotFoundError,
    CapabilityStatus,
    InvalidCapabilityNameError,
    InvalidCapabilityVersionTagError,
)

__all__ = [
    "CAPABILITY_NAME_MAX_LENGTH",
    "CAPABILITY_VERSION_TAG_MAX_LENGTH",
    "Capability",
    "CapabilityAlreadyExistsError",
    "CapabilityCannotDeprecateError",
    "CapabilityCannotVersionError",
    "CapabilityDefined",
    "CapabilityDeprecated",
    "CapabilityEvent",
    "CapabilityName",
    "CapabilityNotFoundError",
    "CapabilitySchemaUpdated",
    "CapabilityStatus",
    "CapabilityVersioned",
    "InvalidCapabilityNameError",
    "InvalidCapabilitySchemaError",
    "InvalidCapabilityVersionTagError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_capability",
    "to_payload",
    "validate_settings_schema",
]
