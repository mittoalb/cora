"""Property-based tests for `version_clearance_template.decide`.

Pins the additive-within-Active decider invariants with Hypothesis:

  - Happy path: an Active state, a same-facility parent lookup, and
    `new_version == state.version + 1` ALWAYS produces exactly one
    `ClearanceTemplateVersioned` event keyed by `state.id`, carrying
    the command's `new_version`, the command's `supersedes_template_id`,
    and the injected `versioned_by` actor.
  - Status guard (L4): any non-Active starting status ALWAYS raises
    `ClearanceTemplateCannotVersionError`.
  - Missing parent: a None `parent_lookup_result` ALWAYS raises
    `ClearanceTemplateNotFoundError`.
  - Facility mismatch (L5): a parent whose `facility_code` differs from
    the child's ALWAYS raises `ClearanceTemplateFacilityMismatchError`.
  - Non-monotonic version (L4): any `new_version != state.version + 1`
    ALWAYS raises `ClearanceTemplateCannotVersionError`.
"""

from datetime import datetime
from uuid import UUID

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from cora.infrastructure.ports.clearance_template_lookup import (
    ClearanceTemplateLookupResult,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplate,
    ClearanceTemplateCannotVersionError,
    ClearanceTemplateCode,
    ClearanceTemplateFacilityMismatchError,
    ClearanceTemplateNotFoundError,
    ClearanceTemplateStatus,
    ClearanceTemplateTitle,
    ClearanceTemplateVersion,
)
from cora.safety.features.version_clearance_template.command import (
    VersionClearanceTemplate,
)
from cora.safety.features.version_clearance_template.decider import decide
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000099"))

_FACILITY_CODES = st.sampled_from(["aps", "maxiv", "esrf"])

_NON_ACTIVE_STATUSES = st.sampled_from(
    [
        ClearanceTemplateStatus.DRAFT,
        ClearanceTemplateStatus.DEPRECATED,
        ClearanceTemplateStatus.WITHDRAWN,
    ]
)


def _state(
    *,
    template_id: UUID,
    facility_code: str,
    version: int,
    status: ClearanceTemplateStatus = ClearanceTemplateStatus.ACTIVE,
) -> ClearanceTemplate:
    return ClearanceTemplate(
        id=template_id,
        facility_code=FacilityCode(facility_code),
        code=ClearanceTemplateCode("parent-template"),
        title=ClearanceTemplateTitle("Parent Template"),
        defined_at=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        defined_by=_TEST_ACTOR_ID,
        status=status,
        version=ClearanceTemplateVersion(version),
    )


def _parent_lookup(
    *,
    supersedes_template_id: UUID,
    facility_code: str,
    version: int,
) -> ClearanceTemplateLookupResult:
    return ClearanceTemplateLookupResult(
        id=supersedes_template_id,
        facility_code=facility_code,
        code="parent-template",
        status=ClearanceTemplateStatus.ACTIVE.value,
        version=version,
    )


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    state_facility=_FACILITY_CODES,
    state_version=st.integers(min_value=1, max_value=20),
    now=aware_datetimes(),
    template_id=st.uuids(),
    supersedes_template_id=st.uuids(),
    versioned_by=st.uuids(),
)
def test_decide_happy_path_emits_single_versioned_event(
    state_facility: str,
    state_version: int,
    now: datetime,
    template_id: UUID,
    supersedes_template_id: UUID,
    versioned_by: UUID,
) -> None:
    """Active state + same-facility parent + monotonic bump yields one event."""
    new_version = state_version + 1
    command = VersionClearanceTemplate(
        template_id=template_id,
        new_version=new_version,
        supersedes_template_id=supersedes_template_id,
    )
    actor = ActorId(versioned_by)

    events = decide(
        state=_state(
            template_id=template_id,
            facility_code=state_facility,
            version=state_version,
        ),
        command=command,
        now=now,
        versioned_by=actor,
        parent_lookup_result=_parent_lookup(
            supersedes_template_id=supersedes_template_id,
            facility_code=state_facility,
            version=state_version,
        ),
    )

    assert len(events) == 1
    event = events[0]
    assert event.template_id == template_id
    assert event.new_version == new_version
    assert event.supersedes_template_id == supersedes_template_id
    assert event.versioned_by == actor
    assert event.occurred_at == now


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    state_facility=_FACILITY_CODES,
    state_version=st.integers(min_value=1, max_value=20),
    status=_NON_ACTIVE_STATUSES,
    now=aware_datetimes(),
    template_id=st.uuids(),
    supersedes_template_id=st.uuids(),
    versioned_by=st.uuids(),
)
def test_decide_rejects_non_active_status(
    state_facility: str,
    state_version: int,
    status: ClearanceTemplateStatus,
    now: datetime,
    template_id: UUID,
    supersedes_template_id: UUID,
    versioned_by: UUID,
) -> None:
    """Any non-Active starting status raises CannotVersion."""
    command = VersionClearanceTemplate(
        template_id=template_id,
        new_version=state_version + 1,
        supersedes_template_id=supersedes_template_id,
    )

    with pytest.raises(ClearanceTemplateCannotVersionError):
        decide(
            state=_state(
                template_id=template_id,
                facility_code=state_facility,
                version=state_version,
                status=status,
            ),
            command=command,
            now=now,
            versioned_by=ActorId(versioned_by),
            parent_lookup_result=_parent_lookup(
                supersedes_template_id=supersedes_template_id,
                facility_code=state_facility,
                version=state_version,
            ),
        )


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    state_facility=_FACILITY_CODES,
    state_version=st.integers(min_value=1, max_value=20),
    now=aware_datetimes(),
    template_id=st.uuids(),
    supersedes_template_id=st.uuids(),
    versioned_by=st.uuids(),
)
def test_decide_rejects_when_parent_lookup_result_is_none(
    state_facility: str,
    state_version: int,
    now: datetime,
    template_id: UUID,
    supersedes_template_id: UUID,
    versioned_by: UUID,
) -> None:
    """A None parent lookup ALWAYS raises ClearanceTemplateNotFoundError."""
    command = VersionClearanceTemplate(
        template_id=template_id,
        new_version=state_version + 1,
        supersedes_template_id=supersedes_template_id,
    )

    with pytest.raises(ClearanceTemplateNotFoundError):
        decide(
            state=_state(
                template_id=template_id,
                facility_code=state_facility,
                version=state_version,
            ),
            command=command,
            now=now,
            versioned_by=ActorId(versioned_by),
            parent_lookup_result=None,
        )


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    state_facility=_FACILITY_CODES,
    parent_facility=_FACILITY_CODES,
    state_version=st.integers(min_value=1, max_value=20),
    now=aware_datetimes(),
    template_id=st.uuids(),
    supersedes_template_id=st.uuids(),
    versioned_by=st.uuids(),
)
def test_decide_rejects_facility_mismatch(
    state_facility: str,
    parent_facility: str,
    state_version: int,
    now: datetime,
    template_id: UUID,
    supersedes_template_id: UUID,
    versioned_by: UUID,
) -> None:
    """A parent in a different facility ALWAYS raises FacilityMismatch."""
    assume(state_facility != parent_facility)
    command = VersionClearanceTemplate(
        template_id=template_id,
        new_version=state_version + 1,
        supersedes_template_id=supersedes_template_id,
    )

    with pytest.raises(ClearanceTemplateFacilityMismatchError):
        decide(
            state=_state(
                template_id=template_id,
                facility_code=state_facility,
                version=state_version,
            ),
            command=command,
            now=now,
            versioned_by=ActorId(versioned_by),
            parent_lookup_result=_parent_lookup(
                supersedes_template_id=supersedes_template_id,
                facility_code=parent_facility,
                version=state_version,
            ),
        )


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    state_facility=_FACILITY_CODES,
    state_version=st.integers(min_value=1, max_value=20),
    new_version=st.integers(min_value=-5, max_value=50),
    now=aware_datetimes(),
    template_id=st.uuids(),
    supersedes_template_id=st.uuids(),
    versioned_by=st.uuids(),
)
def test_decide_rejects_non_monotonic_new_version(
    state_facility: str,
    state_version: int,
    new_version: int,
    now: datetime,
    template_id: UUID,
    supersedes_template_id: UUID,
    versioned_by: UUID,
) -> None:
    """Any new_version not equal to state.version + 1 raises CannotVersion."""
    assume(new_version != state_version + 1)
    command = VersionClearanceTemplate(
        template_id=template_id,
        new_version=new_version,
        supersedes_template_id=supersedes_template_id,
    )

    with pytest.raises(ClearanceTemplateCannotVersionError):
        decide(
            state=_state(
                template_id=template_id,
                facility_code=state_facility,
                version=state_version,
            ),
            command=command,
            now=now,
            versioned_by=ActorId(versioned_by),
            parent_lookup_result=_parent_lookup(
                supersedes_template_id=supersedes_template_id,
                facility_code=state_facility,
                version=state_version,
            ),
        )
