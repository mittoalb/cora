"""Pure-decider tests for `register_clearance` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceAlreadyExistsError,
    ClearanceKind,
    ClearanceTitle,
    HazardDeclaration,
    InvalidClearanceBindingsError,
    InvalidClearanceDeclarationTargetError,
    InvalidClearanceExternalIdError,
    InvalidClearanceTitleError,
    InvalidClearanceValidityWindowError,
    RunBinding,
    SubjectBinding,
)
from cora.safety.aggregates.clearance.hazard_classification import RiskBand
from cora.safety.features import register_clearance
from cora.safety.features.register_clearance import RegisterClearance

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_decide_emits_clearance_registered_when_stream_is_empty() -> None:
    new_id = uuid4()
    rid = uuid4()
    events = register_clearance.decide(
        state=None,
        command=RegisterClearance(
            kind=ClearanceKind.ESAF,
            facility_asset_id=uuid4(),
            title="Pilot ESAF",
            bindings=frozenset({RunBinding(run_id=rid)}),
        ),
        now=_NOW,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert event.clearance_id == new_id
    assert event.kind == "ESAF"
    assert event.title == "Pilot ESAF"
    assert event.bindings == ({"kind": "Run", "id": str(rid)},)
    assert event.declarations == ()
    assert event.risk_band is None
    assert event.external_id is None
    assert event.valid_from is None
    assert event.valid_until is None
    assert event.parent_clearance_id is None
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decide_serializes_multi_binding() -> None:
    sid, aid, rid = uuid4(), uuid4(), uuid4()
    events = register_clearance.decide(
        state=None,
        command=RegisterClearance(
            kind=ClearanceKind.SAF,
            facility_asset_id=uuid4(),
            title="Multi",
            bindings=frozenset({SubjectBinding(subject_id=sid), RunBinding(run_id=rid)}),
        ),
        now=_NOW,
        new_id=aid,
    )
    binding_kinds = {b["kind"] for b in events[0].bindings}
    assert binding_kinds == {"Subject", "Run"}


@pytest.mark.unit
def test_decide_serializes_declaration_with_classifications() -> None:
    sid = uuid4()
    events = register_clearance.decide(
        state=None,
        command=RegisterClearance(
            kind=ClearanceKind.ESAF,
            facility_asset_id=uuid4(),
            title="With hazards",
            bindings=frozenset({SubjectBinding(subject_id=sid)}),
            declarations=frozenset(
                {
                    HazardDeclaration(
                        target=SubjectBinding(subject_id=sid),
                        classifications=frozenset({RiskBand.YELLOW}),
                        mitigations=frozenset({"ppe:gloves"}),
                    )
                }
            ),
            risk_band=RiskBand.YELLOW,
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events[0].declarations) == 1
    assert events[0].risk_band == "Yellow"


@pytest.mark.unit
def test_decide_trims_external_id() -> None:
    events = register_clearance.decide(
        state=None,
        command=RegisterClearance(
            kind=ClearanceKind.ESAF,
            facility_asset_id=uuid4(),
            title="t",
            bindings=frozenset({RunBinding(run_id=uuid4())}),
            external_id="  ESAF-12345  ",
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].external_id == "ESAF-12345"


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Clearance(
        id=uuid4(),
        kind=ClearanceKind.ESAF,
        facility_asset_id=uuid4(),
        title=ClearanceTitle("existing"),
        bindings=frozenset({RunBinding(run_id=uuid4())}),
    )
    with pytest.raises(ClearanceAlreadyExistsError) as exc_info:
        register_clearance.decide(
            state=existing,
            command=RegisterClearance(
                kind=ClearanceKind.ESAF,
                facility_asset_id=uuid4(),
                title="other",
                bindings=frozenset({RunBinding(run_id=uuid4())}),
            ),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.clearance_id == existing.id


@pytest.mark.unit
def test_decide_rejects_empty_title() -> None:
    with pytest.raises(InvalidClearanceTitleError):
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                kind=ClearanceKind.ESAF,
                facility_asset_id=uuid4(),
                title="   ",
                bindings=frozenset({RunBinding(run_id=uuid4())}),
            ),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_too_long_title() -> None:
    with pytest.raises(InvalidClearanceTitleError):
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                kind=ClearanceKind.ESAF,
                facility_asset_id=uuid4(),
                title="a" * 201,
                bindings=frozenset({RunBinding(run_id=uuid4())}),
            ),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_empty_bindings() -> None:
    with pytest.raises(InvalidClearanceBindingsError):
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                kind=ClearanceKind.ESAF,
                facility_asset_id=uuid4(),
                title="t",
                bindings=frozenset(),
            ),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_empty_external_id() -> None:
    with pytest.raises(InvalidClearanceExternalIdError):
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                kind=ClearanceKind.ESAF,
                facility_asset_id=uuid4(),
                title="t",
                bindings=frozenset({RunBinding(run_id=uuid4())}),
                external_id="   ",
            ),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_too_long_external_id() -> None:
    with pytest.raises(InvalidClearanceExternalIdError):
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                kind=ClearanceKind.ESAF,
                facility_asset_id=uuid4(),
                title="t",
                bindings=frozenset({RunBinding(run_id=uuid4())}),
                external_id="a" * 101,
            ),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_inverted_validity_window() -> None:
    later = datetime(2026, 5, 16, tzinfo=UTC)
    earlier = datetime(2026, 5, 15, tzinfo=UTC)
    with pytest.raises(InvalidClearanceValidityWindowError):
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                kind=ClearanceKind.ESAF,
                facility_asset_id=uuid4(),
                title="t",
                bindings=frozenset({RunBinding(run_id=uuid4())}),
                valid_from=later,
                valid_until=earlier,
            ),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_accepts_validity_window_when_only_one_side_provided() -> None:
    """Half-bounded windows are valid; only the inverted-both-sides case fails."""
    register_clearance.decide(
        state=None,
        command=RegisterClearance(
            kind=ClearanceKind.ESAF,
            facility_asset_id=uuid4(),
            title="t",
            bindings=frozenset({RunBinding(run_id=uuid4())}),
            valid_from=_NOW,
            valid_until=None,
        ),
        now=_NOW,
        new_id=uuid4(),
    )


@pytest.mark.unit
def test_decide_rejects_zero_duration_validity_window() -> None:
    """`valid_from == valid_until` is degenerate (zero-duration window can never
    be Active); rejected at decider for the same reason as inverted windows."""
    instant = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
    with pytest.raises(InvalidClearanceValidityWindowError):
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                kind=ClearanceKind.ESAF,
                facility_asset_id=uuid4(),
                title="t",
                bindings=frozenset({RunBinding(run_id=uuid4())}),
                valid_from=instant,
                valid_until=instant,
            ),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_declaration_target_not_in_bindings() -> None:
    """A HazardDeclaration whose target binding is NOT in the Clearance's
    bindings set is incoherent (the Clearance can't gate against an out-of-
    scope target). Rejected at decider per the subset-semantic invariant."""
    in_set_subject = uuid4()
    out_of_set_subject = uuid4()
    with pytest.raises(InvalidClearanceDeclarationTargetError):
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                kind=ClearanceKind.ESAF,
                facility_asset_id=uuid4(),
                title="t",
                bindings=frozenset({SubjectBinding(subject_id=in_set_subject)}),
                declarations=frozenset(
                    {
                        HazardDeclaration(
                            target=SubjectBinding(subject_id=out_of_set_subject),
                        )
                    }
                ),
            ),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_accepts_declaration_target_when_in_bindings() -> None:
    """Counterpart to the rejection test: target IN bindings is the happy path."""
    sid = uuid4()
    register_clearance.decide(
        state=None,
        command=RegisterClearance(
            kind=ClearanceKind.ESAF,
            facility_asset_id=uuid4(),
            title="t",
            bindings=frozenset({SubjectBinding(subject_id=sid)}),
            declarations=frozenset({HazardDeclaration(target=SubjectBinding(subject_id=sid))}),
        ),
        now=_NOW,
        new_id=uuid4(),
    )


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    rid = uuid4()
    cmd = RegisterClearance(
        kind=ClearanceKind.ESAF,
        facility_asset_id=uuid4(),
        title="repeatable",
        bindings=frozenset({RunBinding(run_id=rid)}),
    )
    first = register_clearance.decide(state=None, command=cmd, now=_NOW, new_id=new_id)
    second = register_clearance.decide(state=None, command=cmd, now=_NOW, new_id=new_id)
    assert first == second
