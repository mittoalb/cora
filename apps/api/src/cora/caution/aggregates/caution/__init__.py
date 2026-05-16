"""Caution aggregate: state, enums (status / severity / category / retire-reason),
target discriminated union, bounded-text VOs, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.caution.features.<verb>_caution/` and import from here for state
and event types.

Public surface: enums + VOs + targets + errors + events + evolver +
load_caution. 11b-a ships the foundation (register + supersede +
retire + get); 11b-b adds the projection + list slice; 11b-c adds
the Run.start non-blocking integration via a new `CautionLookup` port.
"""

from cora.caution.aggregates.caution.events import (
    CautionEvent,
    CautionRegistered,
    CautionRetired,
    CautionSuperseded,
    deserialize_target,
    event_type_name,
    from_stored,
    serialize_target,
    to_payload,
)
from cora.caution.aggregates.caution.evolver import evolve, fold
from cora.caution.aggregates.caution.read import load_caution
from cora.caution.aggregates.caution.state import (
    CAUTION_TAG_MAX_LENGTH,
    CAUTION_TEXT_MAX_LENGTH,
    CAUTION_WORKAROUND_MAX_LENGTH,
    AssetTarget,
    Caution,
    CautionAlreadyExistsError,
    CautionCannotRetireError,
    CautionCannotSupersedeError,
    CautionCategory,
    CautionNotFoundError,
    CautionRetireReason,
    CautionSeverity,
    CautionStatus,
    CautionTag,
    CautionTarget,
    CautionText,
    CautionWorkaround,
    InvalidCautionExpiresAtError,
    InvalidCautionSupersedeTargetError,
    InvalidCautionTagError,
    InvalidCautionTextError,
    InvalidCautionWorkaroundError,
    ProcedureTarget,
)

__all__ = [
    "CAUTION_TAG_MAX_LENGTH",
    "CAUTION_TEXT_MAX_LENGTH",
    "CAUTION_WORKAROUND_MAX_LENGTH",
    "AssetTarget",
    "Caution",
    "CautionAlreadyExistsError",
    "CautionCannotRetireError",
    "CautionCannotSupersedeError",
    "CautionCategory",
    "CautionEvent",
    "CautionNotFoundError",
    "CautionRegistered",
    "CautionRetireReason",
    "CautionRetired",
    "CautionSeverity",
    "CautionStatus",
    "CautionSuperseded",
    "CautionTag",
    "CautionTarget",
    "CautionText",
    "CautionWorkaround",
    "InvalidCautionExpiresAtError",
    "InvalidCautionSupersedeTargetError",
    "InvalidCautionTagError",
    "InvalidCautionTextError",
    "InvalidCautionWorkaroundError",
    "ProcedureTarget",
    "deserialize_target",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_caution",
    "serialize_target",
    "to_payload",
]
