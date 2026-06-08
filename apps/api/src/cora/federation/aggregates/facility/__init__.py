"""Re-exports for the Facility aggregate.

Pattern matches `cora.federation.aggregates.credential.__init__`:
events, state, evolver, read helpers, and the deterministic stream-id
helper are all surfaced at the aggregate namespace so slices import
`from cora.federation.aggregates.facility import ...` without reaching
into individual modules.
"""

from cora.federation.aggregates.facility._stream_id import facility_stream_id
from cora.federation.aggregates.facility.events import (
    FacilityDecommissioned,
    FacilityEvent,
    FacilityRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.federation.aggregates.facility.evolver import evolve, fold
from cora.federation.aggregates.facility.read import load_facility
from cora.federation.aggregates.facility.state import (
    Facility,
    FacilityAlreadyExistsError,
    FacilityAreaCannotHaveTrustAnchorsError,
    FacilityAreaMustHaveParentError,
    FacilityCannotDecommissionError,
    FacilityKind,
    FacilityLifecycleTimestamps,
    FacilityName,
    FacilityNotFoundError,
    FacilitySiteCannotHaveParentError,
    FacilityStatus,
    InvalidFacilityNameError,
)

__all__ = [
    "Facility",
    "FacilityAlreadyExistsError",
    "FacilityAreaCannotHaveTrustAnchorsError",
    "FacilityAreaMustHaveParentError",
    "FacilityCannotDecommissionError",
    "FacilityDecommissioned",
    "FacilityEvent",
    "FacilityKind",
    "FacilityLifecycleTimestamps",
    "FacilityName",
    "FacilityNotFoundError",
    "FacilityRegistered",
    "FacilitySiteCannotHaveParentError",
    "FacilityStatus",
    "InvalidFacilityNameError",
    "event_type_name",
    "evolve",
    "facility_stream_id",
    "fold",
    "from_stored",
    "load_facility",
    "to_payload",
]
