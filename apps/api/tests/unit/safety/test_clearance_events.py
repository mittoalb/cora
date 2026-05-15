"""ClearanceEvent serialization round-trips: to_payload + from_stored + helpers."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.safety.aggregates.clearance import (
    AssetBinding,
    ClearanceRegistered,
    ExternalBinding,
    HazardDeclaration,
    ProcedureBinding,
    RunBinding,
    SubjectBinding,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.safety.aggregates.clearance.events import (
    deserialize_binding,
    deserialize_classification,
    deserialize_declaration,
    serialize_binding,
    serialize_classification,
    serialize_declaration,
)
from cora.safety.aggregates.clearance.hazard_classification import (
    GHSPictogram,
    NFPA704Rating,
    RiskBand,
    SchemeCode,
)

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_CLEARANCE_ID = UUID("01900000-0000-7000-8000-000000011001")


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Clearance",
        stream_id=_CLEARANCE_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


# ---------- serialize_binding / deserialize_binding ----------


@pytest.mark.unit
def test_serialize_binding_subject_round_trip() -> None:
    sid = uuid4()
    original = SubjectBinding(subject_id=sid)
    encoded = serialize_binding(original)
    assert encoded == {"kind": "Subject", "id": str(sid)}
    assert deserialize_binding(encoded) == original


@pytest.mark.unit
def test_serialize_binding_asset_round_trip() -> None:
    aid = uuid4()
    original = AssetBinding(asset_id=aid)
    encoded = serialize_binding(original)
    assert encoded == {"kind": "Asset", "id": str(aid)}
    assert deserialize_binding(encoded) == original


@pytest.mark.unit
def test_serialize_binding_run_round_trip() -> None:
    rid = uuid4()
    original = RunBinding(run_id=rid)
    encoded = serialize_binding(original)
    assert encoded == {"kind": "Run", "id": str(rid)}
    assert deserialize_binding(encoded) == original


@pytest.mark.unit
def test_serialize_binding_procedure_round_trip() -> None:
    pid = uuid4()
    original = ProcedureBinding(procedure_id=pid)
    encoded = serialize_binding(original)
    assert encoded == {"kind": "Procedure", "id": str(pid)}
    assert deserialize_binding(encoded) == original


@pytest.mark.unit
def test_serialize_binding_external_round_trip() -> None:
    original = ExternalBinding(scheme="proposal", id="GUP-12345")
    encoded = serialize_binding(original)
    assert encoded == {"kind": "External", "scheme": "proposal", "id": "GUP-12345"}
    assert deserialize_binding(encoded) == original


@pytest.mark.unit
def test_deserialize_binding_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unknown ClearanceBinding kind"):
        deserialize_binding({"kind": "Mystery", "id": "x"})


@pytest.mark.unit
def test_deserialize_binding_rejects_missing_id_field() -> None:
    """Missing inner field is surfaced as ValueError (not KeyError) so callers
    see a single failure mode for contaminated payloads."""
    with pytest.raises(ValueError, match="Malformed ClearanceBinding"):
        deserialize_binding({"kind": "Subject"})


@pytest.mark.unit
def test_deserialize_binding_rejects_missing_kind_field() -> None:
    with pytest.raises(ValueError, match="Malformed ClearanceBinding"):
        deserialize_binding({"id": "x"})


@pytest.mark.unit
def test_deserialize_binding_rejects_non_uuid_id() -> None:
    """UUID() raises ValueError natively; verify the wrap layer still surfaces
    a ValueError consistent with the other malformed-payload paths."""
    with pytest.raises(ValueError):
        deserialize_binding({"kind": "Subject", "id": "not-a-uuid"})


@pytest.mark.unit
def test_deserialize_binding_rejects_external_missing_scheme() -> None:
    with pytest.raises(ValueError, match="Malformed ClearanceBinding"):
        deserialize_binding({"kind": "External", "id": "GUP-1"})


# ---------- serialize_classification / deserialize_classification ----------


@pytest.mark.unit
def test_serialize_classification_nfpa704_round_trip() -> None:
    original = NFPA704Rating(health=2, flammability=1, instability=0, special="OX")
    encoded = serialize_classification(original)
    assert encoded == {
        "kind": "NFPA704",
        "health": 2,
        "flammability": 1,
        "instability": 0,
        "special": "OX",
    }
    assert deserialize_classification(encoded) == original


@pytest.mark.unit
def test_serialize_classification_risk_band_round_trip() -> None:
    encoded = serialize_classification(RiskBand.YELLOW)
    assert encoded == {"kind": "RiskBand", "band": "Yellow"}
    assert deserialize_classification(encoded) == RiskBand.YELLOW


@pytest.mark.unit
def test_serialize_classification_ghs_round_trip() -> None:
    original = GHSPictogram(code="GHS06", statement_codes=frozenset({"H300", "H311"}))
    encoded = serialize_classification(original)
    assert encoded["kind"] == "GHS"
    assert encoded["code"] == "GHS06"
    assert encoded["statement_codes"] == ["H300", "H311"]  # sorted
    assert deserialize_classification(encoded) == original


@pytest.mark.unit
def test_serialize_classification_scheme_round_trip() -> None:
    original = SchemeCode(scheme="ANSI_Z136", code="Class_4", severity_label="extreme")
    encoded = serialize_classification(original)
    assert encoded == {
        "kind": "Scheme",
        "scheme": "ANSI_Z136",
        "code": "Class_4",
        "severity_label": "extreme",
    }
    assert deserialize_classification(encoded) == original


@pytest.mark.unit
def test_deserialize_classification_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unknown HazardClassification kind"):
        deserialize_classification({"kind": "Mystery"})


@pytest.mark.unit
def test_deserialize_classification_rejects_missing_inner_field() -> None:
    """Missing inner NFPA704 health/flammability/instability surfaces as ValueError."""
    with pytest.raises(ValueError, match="Malformed HazardClassification"):
        deserialize_classification({"kind": "NFPA704", "health": 1, "flammability": 0})


@pytest.mark.unit
def test_deserialize_classification_rejects_missing_kind_field() -> None:
    with pytest.raises(ValueError, match="Malformed HazardClassification"):
        deserialize_classification({"health": 1})


# ---------- serialize_declaration / deserialize_declaration ----------


@pytest.mark.unit
def test_serialize_declaration_round_trip() -> None:
    sid = uuid4()
    original = HazardDeclaration(
        target=SubjectBinding(subject_id=sid),
        classifications=frozenset(
            {NFPA704Rating(health=2, flammability=1, instability=0), RiskBand.YELLOW}
        ),
        mitigations=frozenset({"training:hazcom-2026", "ppe:nitrile_gloves"}),
        notes="Sample notes",
    )
    encoded = serialize_declaration(original)
    rebuilt = deserialize_declaration(encoded)
    assert rebuilt.target == original.target
    assert rebuilt.classifications == original.classifications
    assert rebuilt.mitigations == original.mitigations
    assert rebuilt.notes == original.notes


# ---------- ClearanceRegistered ----------


@pytest.mark.unit
def test_clearance_registered_event_type_name() -> None:
    event = ClearanceRegistered(
        clearance_id=_CLEARANCE_ID,
        kind="ESAF",
        facility_asset_id=uuid4(),
        title="t",
        bindings=({"kind": "Run", "id": str(uuid4())},),
        declarations=(),
        risk_band=None,
        external_id=None,
        valid_from=None,
        valid_until=None,
        parent_clearance_id=None,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "ClearanceRegistered"


@pytest.mark.unit
def test_clearance_registered_to_payload_round_trip() -> None:
    rid = uuid4()
    sid = uuid4()
    original = ClearanceRegistered(
        clearance_id=_CLEARANCE_ID,
        kind="ESAF",
        facility_asset_id=uuid4(),
        title="Pilot ESAF for 35-BM",
        bindings=(
            {"kind": "Run", "id": str(rid)},
            {"kind": "Subject", "id": str(sid)},
            {"kind": "External", "scheme": "proposal", "id": "GUP-12345"},
        ),
        declarations=(
            {
                "target": {"kind": "Subject", "id": str(sid)},
                "classifications": [
                    {"kind": "RiskBand", "band": "Yellow"},
                ],
                "mitigations": ["ppe:gloves"],
                "notes": "test",
            },
        ),
        risk_band="Yellow",
        external_id="ESAF-99999",
        valid_from=_NOW,
        valid_until=None,
        parent_clearance_id=None,
        occurred_at=_NOW,
    )
    payload = to_payload(original)
    rebuilt = from_stored(_stored("ClearanceRegistered", payload))
    assert rebuilt == original


@pytest.mark.unit
def test_from_stored_rejects_unknown_event_type() -> None:
    with pytest.raises(ValueError, match="Unknown ClearanceEvent event_type"):
        from_stored(_stored("ImaginaryEvent", {}))


@pytest.mark.unit
def test_clearance_registered_round_trip_handles_optional_datetimes() -> None:
    """valid_from / valid_until / parent_clearance_id None values survive round-trip."""
    parent = uuid4()
    original = ClearanceRegistered(
        clearance_id=_CLEARANCE_ID,
        kind="DOOR",
        facility_asset_id=uuid4(),
        title="t",
        bindings=({"kind": "External", "scheme": "btr", "id": "BTR-1"},),
        declarations=(),
        risk_band="Green",
        external_id=None,
        valid_from=None,
        valid_until=None,
        parent_clearance_id=parent,
        occurred_at=_NOW,
    )
    rebuilt = from_stored(_stored("ClearanceRegistered", to_payload(original)))
    assert isinstance(rebuilt, ClearanceRegistered)
    assert rebuilt.parent_clearance_id == parent
    assert rebuilt.valid_from is None
    assert rebuilt.valid_until is None
