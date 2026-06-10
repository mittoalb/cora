"""Pure decider for the `DefineClearanceTemplate` command.

Pure function: given the current ClearanceTemplate state (None for a fresh
stream) and a `DefineClearanceTemplate` command, returns the events to
append. No I/O, no awaits, no side effects.

`now`, `new_id`, and `defined_by` are injected by the application handler
from the Clock, IdGenerator, and Actor identity sources. `facility_lookup_result`
is injected by the handler after calling `FacilityLookup.lookup_by_code`;
None signals the Facility code does not resolve to a projection row.
"""

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.safety.aggregates.clearance_template import (
    CLEARANCE_TEMPLATE_CODE_MAX_LENGTH,
    ClearanceTemplate,
    ClearanceTemplateAlreadyExistsError,
    ClearanceTemplateDefined,
    ClearanceTemplateFacilityNotFoundError,
    ClearanceTemplateTitle,
    InvalidClearanceTemplateCodeError,
)
from cora.safety.features.define_clearance_template.command import (
    DefineClearanceTemplate,
)
from cora.shared.bounded_text import validate_bounded_text
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId


def decide(
    state: ClearanceTemplate | None,
    command: DefineClearanceTemplate,
    *,
    now: datetime,
    new_id: UUID,
    defined_by: ActorId,
    facility_lookup_result: FacilityLookupResult | None,
) -> list[ClearanceTemplateDefined]:
    """Decide the events produced by defining a new clearance template.

    Invariants:
      - State must be None (genesis-only)
        -> ClearanceTemplateAlreadyExistsError
      - facility_lookup_result must be non-None
        -> ClearanceTemplateFacilityNotFoundError
      - code must be valid -> InvalidClearanceTemplateCodeError
        (via validate_bounded_text)
      - title must be valid -> InvalidClearanceTemplateTitleError
        (via ClearanceTemplateTitle VO)

    `defined_by` is the operator's `ActorId` (definition is always
    operator-driven). Folded onto the event payload.

    `facility_lookup_result.code` is the canonical Facility slug
    threaded onto the event payload, replacing direct echo of
    `command.facility_code` so the cross-BC convergent identity is
    the single source of truth for the wire value.
    """
    if state is not None:
        raise ClearanceTemplateAlreadyExistsError(state.id)

    if facility_lookup_result is None:
        raise ClearanceTemplateFacilityNotFoundError(FacilityCode(command.facility_code))

    code = validate_bounded_text(
        command.code,
        max_length=CLEARANCE_TEMPLATE_CODE_MAX_LENGTH,
        error_class=InvalidClearanceTemplateCodeError,
    )
    title = ClearanceTemplateTitle(command.title)

    return [
        ClearanceTemplateDefined(
            template_id=new_id,
            code=code,
            title=title.value,
            facility_code=facility_lookup_result.code.value,
            version=1,
            supersedes_template_id=None,
            external_ref=command.external_ref,
            occurred_at=now,
            defined_by=defined_by,
        )
    ]
