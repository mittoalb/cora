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
    from uuid import UUID

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
        _seed_in_memory_clearance_template_lookup(kernel, stream_id, facility_code, template_code)
        return

    _log.info(
        "clearance_template_seed.created",
        template_id=str(stream_id),
        facility_code=facility_code.value,
        template_code=template_code,
    )
    _seed_in_memory_clearance_template_lookup(kernel, stream_id, facility_code, template_code)


def _seed_in_memory_clearance_template_lookup(
    kernel: Kernel,
    template_id: UUID,
    facility_code: FacilityCode,
    template_code: str,
) -> None:
    """Mirror the seeded template into the ClearanceTemplateLookup adapter (in-memory path).

    Production wires `PostgresClearanceTemplateLookup` which reads
    `proj_safety_clearance_template_summary`; the projection worker catches
    up the read model from the seeded ClearanceTemplate{Defined,Activated}
    events so the lookup resolves the template within a bookmark tick.

    The in-memory app variant (test runs, the `test` AppEnv) wires
    `InMemoryClearanceTemplateLookup` which has no event-store subscription;
    without an explicit `register(...)` here, the seed leaves the lookup
    empty and downstream `register_clearance` / `amend_clearance` see
    `ClearanceTemplateNotFoundError` (404) even though the template stream
    exists. Duck-type on the adapter's `register` attribute so production's
    `PostgresClearanceTemplateLookup` short-circuits.

    Mirrors the `_seed_in_memory_facility_lookup` precedent in
    `cora.federation._bootstrap`. Active status matches the seed's
    Define + Activate event pair (lifecycle terminal: templates land
    Active and stay Active until an operator deprecate/withdraws).

    Anti-hook: `.register(...)` is a TEST-only seed helper on
    `InMemoryClearanceTemplateLookup`. Do NOT promote it to the
    `ClearanceTemplateLookup` Protocol surface (would force every
    adapter to implement an in-memory seeding shape that has no
    production meaning). This is the SECOND site of the duck-typed
    in-memory seed (after `_seed_in_memory_facility_lookup`); a THIRD
    consumer is the rule-of-three trigger to extract a bounded
    `TestSeedingLookup` Protocol and isinstance-check at all sites.
    """
    register = getattr(kernel.clearance_template_lookup, "register", None)
    if register is None:
        return
    register(
        template_id=template_id,
        facility_code=facility_code.value,
        code=template_code,
        status="Active",
        # The seed writes Define + Activate at version 1 and templates land
        # Active terminal, so version is always 1 here. A future baseline-
        # template bump would need this to read the real version.
        version=1,
    )


__all__ = ["TEN_FORM_TYPES", "seed_clearance_templates"]
