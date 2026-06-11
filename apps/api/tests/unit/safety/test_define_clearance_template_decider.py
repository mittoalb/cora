"""Unit tests for the `define_clearance_template` slice's pure decider.

Pins the genesis-only invariant, the cross-BC Facility binding
handshake (handler-loads + decider-rejects mirror of register_supply
and bind_asset_to_facility), and the input-validation surface of
the template's code and title VOs. The decider is a pure function
over `(state, command, now, new_id, defined_by, facility_lookup_result)`.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.safety.aggregates.clearance_template import (
    CLEARANCE_TEMPLATE_CODE_MAX_LENGTH,
    CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH,
    ClearanceTemplate,
    ClearanceTemplateAlreadyExistsError,
    ClearanceTemplateCode,
    ClearanceTemplateDefined,
    ClearanceTemplateFacilityNotFoundError,
    ClearanceTemplateStatus,
    ClearanceTemplateTitle,
    ClearanceTemplateVersion,
    InvalidClearanceTemplateCodeError,
    InvalidClearanceTemplateTitleError,
)
from cora.safety.features.define_clearance_template import (
    DefineClearanceTemplate,
    decide,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-0000000ce101")
_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000099"))


def _lookup_result(code: str) -> FacilityLookupResult:
    return FacilityLookupResult(
        id=uuid4(),
        code=FacilityCode(code),
        kind="Site",
        status="Active",
        trust_anchor_credential_ids=frozenset[UUID](),
    )


def _existing_template(template_id: UUID) -> ClearanceTemplate:
    return ClearanceTemplate(
        id=template_id,
        facility_code=FacilityCode("aps"),
        code=ClearanceTemplateCode("esaf"),
        title=ClearanceTemplateTitle("ESAF Form"),
        defined_at=_NOW,
        defined_by=_TEST_ACTOR_ID,
        status=ClearanceTemplateStatus.DRAFT,
        version=ClearanceTemplateVersion(1),
    )


@pytest.mark.unit
def test_decide_emits_defined_event_on_happy_path() -> None:
    command = DefineClearanceTemplate(
        code="esaf",
        title="ESAF Form",
        facility_code="aps",
    )
    result = _lookup_result("aps")

    events = decide(
        state=None,
        command=command,
        now=_NOW,
        new_id=_NEW_ID,
        defined_by=_TEST_ACTOR_ID,
        facility_lookup_result=result,
    )

    assert events == [
        ClearanceTemplateDefined(
            template_id=_NEW_ID,
            facility_code="aps",
            code="esaf",
            title="ESAF Form",
            occurred_at=_NOW,
            defined_by=_TEST_ACTOR_ID,
            version=1,
            supersedes_template_id=None,
            external_ref=None,
        )
    ]


@pytest.mark.unit
def test_decide_defaults_version_to_one_and_omits_optional_bindings() -> None:
    command = DefineClearanceTemplate(
        code="esaf",
        title="ESAF Form",
        facility_code="aps",
    )

    events = decide(
        state=None,
        command=command,
        now=_NOW,
        new_id=_NEW_ID,
        defined_by=_TEST_ACTOR_ID,
        facility_lookup_result=_lookup_result("aps"),
    )

    event = events[0]
    assert event.version == 1
    assert event.supersedes_template_id is None
    assert event.external_ref is None


@pytest.mark.unit
def test_decide_threads_external_ref_onto_event_and_emits_null_supersedes() -> None:
    """9A genesis always emits supersedes_template_id=None; the chain
    lookup lands in 9B's version_clearance_template slice. external_ref
    threads straight from the command."""
    command = DefineClearanceTemplate(
        code="esaf",
        title="ESAF Form v2",
        facility_code="aps",
        external_ref="aps://esaf/v2",
    )

    events = decide(
        state=None,
        command=command,
        now=_NOW,
        new_id=_NEW_ID,
        defined_by=_TEST_ACTOR_ID,
        facility_lookup_result=_lookup_result("aps"),
    )

    event = events[0]
    assert event.supersedes_template_id is None
    assert event.external_ref == "aps://esaf/v2"


@pytest.mark.unit
def test_decide_uses_lookup_result_code_not_command_echo() -> None:
    """Source-of-truth: the projection's canonical FacilityCode wins
    over whatever the operator typed (case normalization happens at
    the FacilityLookup adapter)."""
    command = DefineClearanceTemplate(
        code="esaf",
        title="ESAF Form",
        facility_code="aps",
    )
    # Lookup result returns a different code (canonicalized).
    result = _lookup_result("aps-main")

    events = decide(
        state=None,
        command=command,
        now=_NOW,
        new_id=_NEW_ID,
        defined_by=_TEST_ACTOR_ID,
        facility_lookup_result=result,
    )

    assert events[0].facility_code == "aps-main"


@pytest.mark.unit
def test_decide_threads_defined_by_onto_event() -> None:
    command = DefineClearanceTemplate(
        code="esaf",
        title="ESAF Form",
        facility_code="aps",
    )

    events = decide(
        state=None,
        command=command,
        now=_NOW,
        new_id=_NEW_ID,
        defined_by=_TEST_ACTOR_ID,
        facility_lookup_result=_lookup_result("aps"),
    )

    assert events[0].defined_by == _TEST_ACTOR_ID


@pytest.mark.unit
def test_decide_rejects_when_template_stream_already_exists() -> None:
    """Genesis-only: a non-None state means events already exist on
    this deterministic stream id; raise carrying the current template id."""
    template_id = uuid4()
    state = _existing_template(template_id)
    command = DefineClearanceTemplate(
        code="esaf",
        title="ESAF Form",
        facility_code="aps",
    )
    with pytest.raises(ClearanceTemplateAlreadyExistsError) as exc_info:
        decide(
            state=state,
            command=command,
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_TEST_ACTOR_ID,
            facility_lookup_result=_lookup_result("aps"),
        )
    assert exc_info.value.template_id == template_id


@pytest.mark.unit
def test_decide_rejects_when_facility_code_does_not_resolve() -> None:
    command = DefineClearanceTemplate(
        code="esaf",
        title="ESAF Form",
        facility_code="ghost",
    )
    with pytest.raises(ClearanceTemplateFacilityNotFoundError) as exc_info:
        decide(
            state=None,
            command=command,
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_TEST_ACTOR_ID,
            facility_lookup_result=None,
        )
    assert exc_info.value.facility_code == FacilityCode("ghost")


@pytest.mark.unit
def test_decide_rejects_whitespace_only_code() -> None:
    command = DefineClearanceTemplate(
        code="   ",
        title="ESAF Form",
        facility_code="aps",
    )
    with pytest.raises(InvalidClearanceTemplateCodeError) as exc_info:
        decide(
            state=None,
            command=command,
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_TEST_ACTOR_ID,
            facility_lookup_result=_lookup_result("aps"),
        )
    assert exc_info.value.value == "   "


@pytest.mark.unit
def test_decide_rejects_over_length_code() -> None:
    over_length = "a" * (CLEARANCE_TEMPLATE_CODE_MAX_LENGTH + 1)
    command = DefineClearanceTemplate(
        code=over_length,
        title="ESAF Form",
        facility_code="aps",
    )
    with pytest.raises(InvalidClearanceTemplateCodeError) as exc_info:
        decide(
            state=None,
            command=command,
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_TEST_ACTOR_ID,
            facility_lookup_result=_lookup_result("aps"),
        )
    assert exc_info.value.value == over_length


@pytest.mark.unit
def test_decide_rejects_whitespace_only_title() -> None:
    command = DefineClearanceTemplate(
        code="esaf",
        title="   ",
        facility_code="aps",
    )
    with pytest.raises(InvalidClearanceTemplateTitleError) as exc_info:
        decide(
            state=None,
            command=command,
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_TEST_ACTOR_ID,
            facility_lookup_result=_lookup_result("aps"),
        )
    assert exc_info.value.value == "   "


@pytest.mark.unit
def test_decide_rejects_over_length_title() -> None:
    over_length = "a" * (CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH + 1)
    command = DefineClearanceTemplate(
        code="esaf",
        title=over_length,
        facility_code="aps",
    )
    with pytest.raises(InvalidClearanceTemplateTitleError) as exc_info:
        decide(
            state=None,
            command=command,
            now=_NOW,
            new_id=_NEW_ID,
            defined_by=_TEST_ACTOR_ID,
            facility_lookup_result=_lookup_result("aps"),
        )
    assert exc_info.value.value == over_length
