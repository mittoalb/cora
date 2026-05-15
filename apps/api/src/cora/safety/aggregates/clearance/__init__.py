"""Clearance aggregate: state, enums (status / kind), bindings, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.safety.features.<verb>_clearance/` and import from here for state
and event types.

Public surface: enums + VOs + bindings + errors + events + evolver +
load_clearance. 11a-a ships the genesis (Defined-only); 11a-b adds the
6 FSM-closure events + slices; 11a-c adds the 3 terminal/amendment
events + slices.
"""

from cora.safety.aggregates.clearance.events import (
    ClearanceEvent,
    ClearanceRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.safety.aggregates.clearance.evolver import evolve, fold
from cora.safety.aggregates.clearance.read import load_clearance
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_EXPIRE_REASON_MAX_LENGTH,
    CLEARANCE_EXTERNAL_BINDING_ID_MAX_LENGTH,
    CLEARANCE_EXTERNAL_BINDING_SCHEME_MAX_LENGTH,
    CLEARANCE_EXTERNAL_ID_MAX_LENGTH,
    CLEARANCE_HAZARD_NOTES_MAX_LENGTH,
    CLEARANCE_MITIGATION_REF_MAX_LENGTH,
    CLEARANCE_REJECT_REASON_MAX_LENGTH,
    CLEARANCE_REVIEWER_NOTES_MAX_LENGTH,
    CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
    CLEARANCE_TITLE_MAX_LENGTH,
    AssetBinding,
    Clearance,
    ClearanceAlreadyExistsError,
    ClearanceBinding,
    ClearanceKind,
    ClearanceNotFoundError,
    ClearanceStatus,
    ClearanceTitle,
    ExternalBinding,
    HazardDeclaration,
    InvalidClearanceBindingsError,
    InvalidClearanceDeclarationTargetError,
    InvalidClearanceExternalBindingError,
    InvalidClearanceExternalIdError,
    InvalidClearanceHazardNotesError,
    InvalidClearanceMitigationRefError,
    InvalidClearanceTitleError,
    InvalidClearanceValidityWindowError,
    ProcedureBinding,
    ReviewerStep,
    RunBinding,
    SubjectBinding,
)

__all__ = [
    "CLEARANCE_EXPIRE_REASON_MAX_LENGTH",
    "CLEARANCE_EXTERNAL_BINDING_ID_MAX_LENGTH",
    "CLEARANCE_EXTERNAL_BINDING_SCHEME_MAX_LENGTH",
    "CLEARANCE_EXTERNAL_ID_MAX_LENGTH",
    "CLEARANCE_HAZARD_NOTES_MAX_LENGTH",
    "CLEARANCE_MITIGATION_REF_MAX_LENGTH",
    "CLEARANCE_REJECT_REASON_MAX_LENGTH",
    "CLEARANCE_REVIEWER_NOTES_MAX_LENGTH",
    "CLEARANCE_REVIEWER_ROLE_MAX_LENGTH",
    "CLEARANCE_TITLE_MAX_LENGTH",
    "AssetBinding",
    "Clearance",
    "ClearanceAlreadyExistsError",
    "ClearanceBinding",
    "ClearanceEvent",
    "ClearanceKind",
    "ClearanceNotFoundError",
    "ClearanceRegistered",
    "ClearanceStatus",
    "ClearanceTitle",
    "ExternalBinding",
    "HazardDeclaration",
    "InvalidClearanceBindingsError",
    "InvalidClearanceDeclarationTargetError",
    "InvalidClearanceExternalBindingError",
    "InvalidClearanceExternalIdError",
    "InvalidClearanceHazardNotesError",
    "InvalidClearanceMitigationRefError",
    "InvalidClearanceTitleError",
    "InvalidClearanceValidityWindowError",
    "ProcedureBinding",
    "ReviewerStep",
    "RunBinding",
    "SubjectBinding",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_clearance",
    "to_payload",
]
