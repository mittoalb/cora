"""Unit tests for the `activate_clearance_template` slice's pure decider.

Pins the `Draft -> Active` strict-not-idempotent transition: only a Draft
state activates; missing state raises `ClearanceTemplateNotFoundError`; any
other status raises `ClearanceTemplateCannotActivateError` carrying the
current status. The decider is a pure function over
`(state, command, now, activated_by)` and threads the activator's ActorId
onto the emitted event.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.safety.aggregates.clearance_template import (
    ClearanceTemplate,
    ClearanceTemplateActivated,
    ClearanceTemplateCannotActivateError,
    ClearanceTemplateCode,
    ClearanceTemplateNotFoundError,
    ClearanceTemplateStatus,
    ClearanceTemplateTitle,
    ClearanceTemplateVersion,
)
from cora.safety.features.activate_clearance_template import (
    ActivateClearanceTemplate,
    decide,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_DEFINED_AT = datetime(2026, 6, 9, 9, 0, 0, tzinfo=UTC)
_DEFINER_ID = ActorId(UUID("00000000-0000-0000-0000-000000000011"))
_ACTIVATOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000099"))


def _template(
    *,
    template_id: UUID,
    status: ClearanceTemplateStatus = ClearanceTemplateStatus.DRAFT,
) -> ClearanceTemplate:
    return ClearanceTemplate(
        id=template_id,
        facility_code=FacilityCode("aps"),
        code=ClearanceTemplateCode("esaf"),
        title=ClearanceTemplateTitle("ESAF Form"),
        defined_at=_DEFINED_AT,
        defined_by=_DEFINER_ID,
        status=status,
        version=ClearanceTemplateVersion(1),
    )


@pytest.mark.unit
def test_decide_emits_activated_event_on_happy_path() -> None:
    template_id = uuid4()
    state = _template(template_id=template_id, status=ClearanceTemplateStatus.DRAFT)
    command = ActivateClearanceTemplate(template_id=template_id)

    events = decide(
        state=state,
        command=command,
        now=_NOW,
        activated_by=_ACTIVATOR_ID,
    )

    assert events == [
        ClearanceTemplateActivated(
            template_id=template_id,
            occurred_at=_NOW,
            activated_by=_ACTIVATOR_ID,
        )
    ]


@pytest.mark.unit
def test_decide_rejects_when_state_is_none() -> None:
    template_id = uuid4()
    command = ActivateClearanceTemplate(template_id=template_id)

    with pytest.raises(ClearanceTemplateNotFoundError) as exc_info:
        decide(
            state=None,
            command=command,
            now=_NOW,
            activated_by=_ACTIVATOR_ID,
        )
    assert exc_info.value.template_id == template_id


@pytest.mark.unit
def test_decide_rejects_when_status_is_active() -> None:
    template_id = uuid4()
    state = _template(template_id=template_id, status=ClearanceTemplateStatus.ACTIVE)
    command = ActivateClearanceTemplate(template_id=template_id)

    with pytest.raises(ClearanceTemplateCannotActivateError) as exc_info:
        decide(
            state=state,
            command=command,
            now=_NOW,
            activated_by=_ACTIVATOR_ID,
        )
    assert exc_info.value.template_id == template_id
    assert exc_info.value.current_status == ClearanceTemplateStatus.ACTIVE


@pytest.mark.unit
def test_decide_rejects_when_status_is_deprecated() -> None:
    template_id = uuid4()
    state = _template(template_id=template_id, status=ClearanceTemplateStatus.DEPRECATED)
    command = ActivateClearanceTemplate(template_id=template_id)

    with pytest.raises(ClearanceTemplateCannotActivateError) as exc_info:
        decide(
            state=state,
            command=command,
            now=_NOW,
            activated_by=_ACTIVATOR_ID,
        )
    assert exc_info.value.template_id == template_id
    assert exc_info.value.current_status == ClearanceTemplateStatus.DEPRECATED


@pytest.mark.unit
def test_decide_rejects_when_status_is_withdrawn() -> None:
    template_id = uuid4()
    state = _template(template_id=template_id, status=ClearanceTemplateStatus.WITHDRAWN)
    command = ActivateClearanceTemplate(template_id=template_id)

    with pytest.raises(ClearanceTemplateCannotActivateError) as exc_info:
        decide(
            state=state,
            command=command,
            now=_NOW,
            activated_by=_ACTIVATOR_ID,
        )
    assert exc_info.value.template_id == template_id
    assert exc_info.value.current_status == ClearanceTemplateStatus.WITHDRAWN


@pytest.mark.unit
def test_decide_threads_activated_by_onto_event() -> None:
    template_id = uuid4()
    state = _template(template_id=template_id, status=ClearanceTemplateStatus.DRAFT)
    command = ActivateClearanceTemplate(template_id=template_id)
    distinct_actor = ActorId(UUID("00000000-0000-0000-0000-0000000000aa"))

    events = decide(
        state=state,
        command=command,
        now=_NOW,
        activated_by=distinct_actor,
    )

    assert events[0].activated_by == distinct_actor
