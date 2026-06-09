"""Permit aggregate: state, FSM, directional terms, errors, events, evolver, read repo.

Pattern matches `cora.calibration.aggregates.calibration.__init__`:
events, state, evolver, and read are all surfaced at the aggregate
namespace so slices import
`from cora.federation.aggregates.permit import ...` without reaching
into individual modules. Errors are inlined in `state.py` (matches
the Calibration / Caution / Supply / Clearance precedent); no
separate `errors.py` module.

Defines the canonical `AbiTier` StrEnum (lives here as Permit's
home) re-imported by the seal aggregate; hoist to a shared
federation `_value_types.py` module when a second shared symbol
fires rule-of-three.

`terms` is a tagged union (`OutboundTerms | InboundTerms`) following
the `Observation` polymorphism precedent; the `direction` enum on the
root mirrors `type(terms)` for read-side query convenience.
"""

from cora.federation.aggregates.permit.events import (
    PermitActivated,
    PermitDefined,
    PermitEvent,
    PermitResumed,
    PermitRevoked,
    PermitSuspended,
    deserialize_terms,
    event_type_name,
    from_stored,
    serialize_terms,
    to_payload,
)
from cora.federation.aggregates.permit.evolver import evolve, fold
from cora.federation.aggregates.permit.read import (
    PermitLifecycleTimestamps,
    is_active,
    is_inbound,
    is_outbound,
    is_revoked,
    load_permit,
    load_permit_timestamps,
)
from cora.federation.aggregates.permit.state import (
    AbiTier,
    Direction,
    InboundTerms,
    InvalidPermitScopeError,
    OnwardActionScope,
    OutboundTerms,
    Permit,
    PermitAlreadyExistsError,
    PermitCannotActivateError,
    PermitCannotResumeError,
    PermitCannotRevokeError,
    PermitCannotSuspendError,
    PermitNotFoundError,
    PermitScopeCollapseError,
    PermitStatus,
    ReadScope,
    ReceiptKind,
    ScopeRef,
    UnsupportedCanonicalizationVersionError,
)

__all__ = [
    "AbiTier",
    "Direction",
    "InboundTerms",
    "InvalidPermitScopeError",
    "OnwardActionScope",
    "OutboundTerms",
    "Permit",
    "PermitActivated",
    "PermitAlreadyExistsError",
    "PermitCannotActivateError",
    "PermitCannotResumeError",
    "PermitCannotRevokeError",
    "PermitCannotSuspendError",
    "PermitDefined",
    "PermitEvent",
    "PermitLifecycleTimestamps",
    "PermitNotFoundError",
    "PermitResumed",
    "PermitRevoked",
    "PermitScopeCollapseError",
    "PermitStatus",
    "PermitSuspended",
    "ReadScope",
    "ReceiptKind",
    "ScopeRef",
    "UnsupportedCanonicalizationVersionError",
    "deserialize_terms",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "is_active",
    "is_inbound",
    "is_outbound",
    "is_revoked",
    "load_permit",
    "load_permit_timestamps",
    "serialize_terms",
    "to_payload",
]
