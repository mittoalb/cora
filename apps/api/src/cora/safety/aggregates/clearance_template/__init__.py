"""Clearance template aggregate: state, events, evolver, errors, value objects.

The `ClearanceTemplate` aggregate defines reusable form templates for safety
clearances across a facility. Same FSM (`Draft -> Active -> Deprecated ->
Withdrawn`), with facility-scoped uniqueness on (facility_code, code).

Template-tier aggregate emits "Defined" genesis events (not "Registered").
`ClearanceTemplateDefined` is the genesis event; FSM transitions (Activate,
Deprecate, Withdraw) land in subsequent slices (9B+9C).

Stream ID is deterministically derived from `(facility_code, template_code)`
via UUID5 over a fixed namespace, enabling idempotent day-one registration.

Vertical slices that operate on this aggregate live under
`cora.safety.features.<verb>_clearance_template/` and import from here for
state and event types.
"""

from cora.safety.aggregates.clearance_template._stream_id import (
    clearance_template_stream_id,
)
from cora.safety.aggregates.clearance_template._value_types import (
    CLEARANCE_TEMPLATE_CODE_MAX_LENGTH,
    CLEARANCE_TEMPLATE_EXTERNAL_REF_MAX_LENGTH,
    CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH,
    ClearanceTemplateCode,
    ClearanceTemplateId,
    ClearanceTemplateTitle,
    ClearanceTemplateVersion,
    InvalidClearanceTemplateCodeError,
    InvalidClearanceTemplateTitleError,
    InvalidClearanceTemplateVersionError,
)
from cora.safety.aggregates.clearance_template.events import (
    ClearanceTemplateDefined,
    ClearanceTemplateEvent,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.safety.aggregates.clearance_template.evolver import evolve, fold
from cora.safety.aggregates.clearance_template.read import load_clearance_template
from cora.safety.aggregates.clearance_template.state import (
    ClearanceTemplate,
    ClearanceTemplateAlreadyExistsError,
    ClearanceTemplateFacilityNotFoundError,
    ClearanceTemplateNotFoundError,
    ClearanceTemplateStatus,
)

__all__ = [
    "CLEARANCE_TEMPLATE_CODE_MAX_LENGTH",
    "CLEARANCE_TEMPLATE_EXTERNAL_REF_MAX_LENGTH",
    "CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH",
    "ClearanceTemplate",
    "ClearanceTemplateAlreadyExistsError",
    "ClearanceTemplateCode",
    "ClearanceTemplateDefined",
    "ClearanceTemplateEvent",
    "ClearanceTemplateFacilityNotFoundError",
    "ClearanceTemplateId",
    "ClearanceTemplateNotFoundError",
    "ClearanceTemplateStatus",
    "ClearanceTemplateTitle",
    "ClearanceTemplateVersion",
    "InvalidClearanceTemplateCodeError",
    "InvalidClearanceTemplateTitleError",
    "InvalidClearanceTemplateVersionError",
    "clearance_template_stream_id",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_clearance_template",
    "to_payload",
]
