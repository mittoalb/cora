"""Property-based tests for `define_clearance_template.decide`.

Pins the genesis-only decider invariants with Hypothesis:

  - Determinism: a single `ClearanceTemplateDefined` event is emitted
    on the happy path (length-1 invariant) with `template_id ==
    new_id` for every valid (code, title, facility_code, now, new_id).
  - Source-of-truth: the emitted event's `facility_code` equals
    `facility_lookup_result.code.value`, never an echo of the
    command's raw `facility_code` string.
  - Trim convention: the emitted event's `code` equals
    `command.code.strip()` per the bounded_name VO contract.
  - Genesis-only: a non-None state ALWAYS raises
    `ClearanceTemplateAlreadyExistsError` regardless of payload.
  - Missing facility: a None `facility_lookup_result` ALWAYS raises
    `ClearanceTemplateFacilityNotFoundError`.
  - Empty / whitespace code: ALWAYS raises
    `InvalidClearanceTemplateCodeError`.
  - Empty / whitespace title: ALWAYS raises
    `InvalidClearanceTemplateTitleError`.

Also pins (architecture) that the decider module exposes a `decide`
callable at the canonical import path.
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplate,
    ClearanceTemplateAlreadyExistsError,
    ClearanceTemplateCode,
    ClearanceTemplateFacilityNotFoundError,
    ClearanceTemplateStatus,
    ClearanceTemplateTitle,
    ClearanceTemplateVersion,
    InvalidClearanceTemplateCodeError,
    InvalidClearanceTemplateTitleError,
)
from cora.safety.features.define_clearance_template import decider as decider_module
from cora.safety.features.define_clearance_template.command import (
    DefineClearanceTemplate,
)
from cora.safety.features.define_clearance_template.decider import decide
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000099"))

_FACILITY_CODES = st.sampled_from(["aps", "maxiv", "esrf", "diamond", "spring8", "cora"])

_VALID_CODES = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=50,
)

_VALID_TITLES = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=200,
)

_WHITESPACE_STRINGS = st.sampled_from(["", " ", "  ", "\t", "\n", " \t\n ", "   \t"])


def _lookup_result(code: str) -> FacilityLookupResult:
    return FacilityLookupResult(
        id=uuid4(),
        code=FacilityCode(code),
        kind="Site",
        status="Active",
        trust_anchor_credential_ids=frozenset[UUID](),
    )


def _existing_template(template_id: UUID, facility_code: str) -> ClearanceTemplate:
    return ClearanceTemplate(
        id=template_id,
        facility_code=FacilityCode(facility_code),
        code=ClearanceTemplateCode("preexisting"),
        title=ClearanceTemplateTitle("Preexisting Template"),
        defined_at=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        defined_by=_TEST_ACTOR_ID,
        status=ClearanceTemplateStatus.DRAFT,
        version=ClearanceTemplateVersion(1),
    )


@pytest.mark.architecture
@pytest.mark.unit
def test_decider_module_exposes_decide_callable() -> None:
    """The `decide` symbol must live at the canonical slice path."""
    assert callable(decider_module.decide)


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    code=_VALID_CODES,
    title=_VALID_TITLES,
    facility_code=_FACILITY_CODES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_decide_emits_single_event_with_injected_new_id(
    code: str,
    title: str,
    facility_code: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Genesis happy path returns exactly one event keyed by `new_id`."""
    command = DefineClearanceTemplate(
        code=code,
        title=title,
        facility_code=facility_code,
    )

    events = decide(
        state=None,
        command=command,
        now=now,
        new_id=new_id,
        defined_by=_TEST_ACTOR_ID,
        facility_lookup_result=_lookup_result(facility_code),
    )

    assert len(events) == 1
    assert events[0].template_id == new_id


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    code=_VALID_CODES,
    title=_VALID_TITLES,
    command_facility_code=_FACILITY_CODES,
    lookup_facility_code=_FACILITY_CODES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_decide_event_facility_code_equals_lookup_not_command(
    code: str,
    title: str,
    command_facility_code: str,
    lookup_facility_code: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Event's facility_code is the lookup's canonical value, not the command echo."""
    command = DefineClearanceTemplate(
        code=code,
        title=title,
        facility_code=command_facility_code,
    )

    events = decide(
        state=None,
        command=command,
        now=now,
        new_id=new_id,
        defined_by=_TEST_ACTOR_ID,
        facility_lookup_result=_lookup_result(lookup_facility_code),
    )

    assert events[0].facility_code == lookup_facility_code


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    code=_VALID_CODES,
    title=_VALID_TITLES,
    facility_code=_FACILITY_CODES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_decide_event_code_equals_trimmed_command_code(
    code: str,
    title: str,
    facility_code: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """`bounded_name` trims; the emitted event mirrors that trim."""
    padded_code = f"  {code}  "
    command = DefineClearanceTemplate(
        code=padded_code,
        title=title,
        facility_code=facility_code,
    )

    events = decide(
        state=None,
        command=command,
        now=now,
        new_id=new_id,
        defined_by=_TEST_ACTOR_ID,
        facility_lookup_result=_lookup_result(facility_code),
    )

    assert events[0].code == padded_code.strip()


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    code=_VALID_CODES,
    title=_VALID_TITLES,
    facility_code=_FACILITY_CODES,
    now=aware_datetimes(),
    new_id=st.uuids(),
    existing_id=st.uuids(),
)
def test_decide_rejects_when_state_is_not_none(
    code: str,
    title: str,
    facility_code: str,
    now: datetime,
    new_id: UUID,
    existing_id: UUID,
) -> None:
    """Genesis-only: any non-None state raises AlreadyExists."""
    command = DefineClearanceTemplate(
        code=code,
        title=title,
        facility_code=facility_code,
    )

    with pytest.raises(ClearanceTemplateAlreadyExistsError):
        decide(
            state=_existing_template(existing_id, facility_code),
            command=command,
            now=now,
            new_id=new_id,
            defined_by=_TEST_ACTOR_ID,
            facility_lookup_result=_lookup_result(facility_code),
        )


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    code=_VALID_CODES,
    title=_VALID_TITLES,
    facility_code=_FACILITY_CODES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_decide_rejects_when_facility_lookup_result_is_none(
    code: str,
    title: str,
    facility_code: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """A None lookup result ALWAYS raises FacilityNotFound."""
    command = DefineClearanceTemplate(
        code=code,
        title=title,
        facility_code=facility_code,
    )

    with pytest.raises(ClearanceTemplateFacilityNotFoundError):
        decide(
            state=None,
            command=command,
            now=now,
            new_id=new_id,
            defined_by=_TEST_ACTOR_ID,
            facility_lookup_result=None,
        )


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    blank_code=_WHITESPACE_STRINGS,
    title=_VALID_TITLES,
    facility_code=_FACILITY_CODES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_decide_rejects_blank_or_whitespace_code(
    blank_code: str,
    title: str,
    facility_code: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any empty / whitespace code value raises InvalidCode."""
    command = DefineClearanceTemplate(
        code=blank_code,
        title=title,
        facility_code=facility_code,
    )

    with pytest.raises(InvalidClearanceTemplateCodeError):
        decide(
            state=None,
            command=command,
            now=now,
            new_id=new_id,
            defined_by=_TEST_ACTOR_ID,
            facility_lookup_result=_lookup_result(facility_code),
        )


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    code=_VALID_CODES,
    blank_title=_WHITESPACE_STRINGS,
    facility_code=_FACILITY_CODES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_decide_rejects_blank_or_whitespace_title(
    code: str,
    blank_title: str,
    facility_code: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any empty / whitespace title value raises InvalidTitle."""
    command = DefineClearanceTemplate(
        code=code,
        title=blank_title,
        facility_code=facility_code,
    )

    with pytest.raises(InvalidClearanceTemplateTitleError):
        decide(
            state=None,
            command=command,
            now=now,
            new_id=new_id,
            defined_by=_TEST_ACTOR_ID,
            facility_lookup_result=_lookup_result(facility_code),
        )
