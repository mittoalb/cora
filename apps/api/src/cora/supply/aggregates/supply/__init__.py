"""Supply aggregate: state, enums (status / scope / trigger), errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.supply.features.<verb>_supply/` and import from here for state
and event types.

Phase 10a-a public surface: enums + VOs + errors + events + evolver
+ load_supply. Phase 10a-b adds 4 more transition events + 4 more
errors when the degradation/recovery cycle ships.
"""

from cora.supply.aggregates.supply.events import (
    SupplyEvent,
    SupplyMarkedAvailable,
    SupplyRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.supply.aggregates.supply.evolver import evolve, fold
from cora.supply.aggregates.supply.read import load_supply
from cora.supply.aggregates.supply.state import (
    SUPPLY_KIND_MAX_LENGTH,
    SUPPLY_NAME_MAX_LENGTH,
    SUPPLY_REASON_MAX_LENGTH,
    InvalidSupplyKindError,
    InvalidSupplyNameError,
    InvalidSupplyReasonError,
    Supply,
    SupplyAlreadyExistsError,
    SupplyCannotMarkAvailableError,
    SupplyName,
    SupplyNotFoundError,
    SupplyReason,
    SupplyScope,
    SupplyStatus,
    TriggerSource,
)

__all__ = [
    "SUPPLY_KIND_MAX_LENGTH",
    "SUPPLY_NAME_MAX_LENGTH",
    "SUPPLY_REASON_MAX_LENGTH",
    "InvalidSupplyKindError",
    "InvalidSupplyNameError",
    "InvalidSupplyReasonError",
    "Supply",
    "SupplyAlreadyExistsError",
    "SupplyCannotMarkAvailableError",
    "SupplyEvent",
    "SupplyMarkedAvailable",
    "SupplyName",
    "SupplyNotFoundError",
    "SupplyReason",
    "SupplyRegistered",
    "SupplyScope",
    "SupplyStatus",
    "TriggerSource",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_supply",
    "to_payload",
]
