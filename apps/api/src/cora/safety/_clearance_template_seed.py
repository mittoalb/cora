"""Safety BC lifespan hook: seeds the baseline ClearanceTemplate set per Active Facility.

Per [[project_slice9_design]] L8, every CORA deployment seeds a fixed
set of ten baseline form-type templates for each Active Facility at
lifespan startup. The form-type vocabulary spans the major synchrotron
operating models so the same Safety BC can host clearances at any
facility CORA federates with:

  - ESAF   -- APS Experiment Safety Assessment Form
  - SAF    -- NSLS-II Safety Approval Form
  - AForm  -- ESRF A Form
  - DUO    -- MAX IV Digital User Office Form
  - ESRA   -- MAX IV Experimental Safety Review Application
  - ERA    -- DLS Experimental Risk Assessment
  - PLHD   -- DLS Procedure Local Hazard Declaration
  - DOOR   -- DESY DOOR Form
  - BTR    -- SLAC Beam Time Request
  - Form9  -- SPring-8 Form 9

(See [[project_safety_clearance_design]] for the facility-to-form-type
mapping rationale.) Operators may add more templates via the
define_clearance_template slice; the baseline set is the lifespan
guarantee, not the cap.

Each (facility, template) pair lands as a Define + Activate event pair
written atomically through a single `event_store.append_streams` call
with one `StreamAppend(expected_version=0)`. Idempotency is anchored on
the deterministic `clearance_template_stream_id(facility_code,
template_code)` derivation per L7: the second boot collides on
expected_version=0 and surfaces `ConcurrencyError`, which this hook
swallows as the "already seeded" signal. Safe to call on every app
boot.

The hook fans out one append per (facility, template); failures on one
pair do not block subsequent pairs (each is its own atomic unit). The
ten-template set lands in Active status so register_clearance can bind
against it immediately without an additional operator action.

The acting principal is `SYSTEM_PRINCIPAL_ID` per the
`bootstrap_federation` + `seed_agent` precedents: the seed is a
deployment-stable system action, not an operator command.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports.event_store import ConcurrencyError, StreamAppend
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateActivated,
    ClearanceTemplateDefined,
    clearance_template_stream_id,
    event_type_name,
    to_payload,
)

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel
    from cora.shared.facility_code import FacilityCode


TEN_FORM_TYPES: tuple[str, ...] = (
    "ESAF",
    "SAF",
    "AForm",
    "DUO",
    "ESRA",
    "ERA",
    "PLHD",
    "DOOR",
    "BTR",
    "Form9",
)

_STREAM_TYPE = "ClearanceTemplate"
_COMMAND_NAME = "seed_clearance_templates"

_log = get_logger(__name__)

_DEFAULT_FACILITY_TITLES: dict[str, str] = {
    "ESAF": "Experiment Safety Assessment Form",
    "SAF": "Safety Approval Form",
    "AForm": "ESRF A Form",
    "DUO": "MAX IV Digital User Office Form",
    "ESRA": "MAX IV Experimental Safety Review Application",
    "ERA": "DLS Experimental Risk Assessment",
    "PLHD": "DLS Procedure Local Hazard Declaration",
    "DOOR": "DESY DOOR Form",
    "BTR": "SLAC Beam Time Request",
    "Form9": "SPring-8 Form 9",
}


async def seed_clearance_templates(kernel: Kernel) -> None:
    """Seed the baseline ClearanceTemplate set for every Active Facility (idempotent).

    No-op per (facility, template) pair if that template is already
    seeded; logs the outcome either way. Safe to call on every app
    boot.
    """
    active_facilities = await kernel.facility_lookup.list_active()
    for facility in active_facilities:
        for template_code in TEN_FORM_TYPES:
            await _seed_one_template(kernel, facility.code, template_code)


async def _seed_one_template(
    kernel: Kernel, facility_code: FacilityCode, template_code: str
) -> None:
    """Seed one (facility, template) pair as an atomic Define + Activate write."""
    now = kernel.clock.now()
    stream_id = clearance_template_stream_id(facility_code.value, template_code)
    title = _DEFAULT_FACILITY_TITLES[template_code]
    correlation_id = kernel.id_generator.new_id()

    defined_event = ClearanceTemplateDefined(
        template_id=stream_id,
        facility_code=facility_code.value,
        code=template_code,
        title=title,
        occurred_at=now,
        defined_by=SYSTEM_PRINCIPAL_ID,
    )
    activated_event = ClearanceTemplateActivated(
        template_id=stream_id,
        occurred_at=now,
        activated_by=SYSTEM_PRINCIPAL_ID,
    )

    defined_new_event = to_new_event(
        event_type=event_type_name(defined_event),
        payload=to_payload(defined_event),
        occurred_at=now,
        event_id=kernel.id_generator.new_id(),
        command_name=_COMMAND_NAME,
        correlation_id=correlation_id,
        causation_id=None,
        principal_id=SYSTEM_PRINCIPAL_ID,
    )
    activated_new_event = to_new_event(
        event_type=event_type_name(activated_event),
        payload=to_payload(activated_event),
        occurred_at=now,
        event_id=kernel.id_generator.new_id(),
        command_name=_COMMAND_NAME,
        correlation_id=correlation_id,
        causation_id=None,
        principal_id=SYSTEM_PRINCIPAL_ID,
    )

    try:
        await kernel.event_store.append_streams(
            [
                StreamAppend(
                    stream_type=_STREAM_TYPE,
                    stream_id=stream_id,
                    expected_version=0,
                    events=[defined_new_event, activated_new_event],
                ),
            ]
        )
    except ConcurrencyError:
        _log.info(
            "clearance_template_seed.already_present",
            template_id=str(stream_id),
            facility_code=facility_code.value,
            template_code=template_code,
        )
        return

    _log.info(
        "clearance_template_seed.created",
        template_id=str(stream_id),
        facility_code=facility_code.value,
        template_code=template_code,
    )


__all__ = ["TEN_FORM_TYPES", "seed_clearance_templates"]
