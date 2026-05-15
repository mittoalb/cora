"""Domain events emitted by the Clearance aggregate, plus the discriminated union.

Phase 11a-a ships only `ClearanceRegistered` (genesis -> Defined).
Phase 11a-b adds the 6 FSM-closure events (Submitted / UnderReview /
ReviewStepRecorded / Approved / Rejected / Activated). Phase 11a-c
adds the 3 terminal/amendment events (Expired / AmendmentInitiated /
Superseded). Per the per-sub-phase event-introduction precedent
(Supply 10a-a/b, Operation 10c-a/b/c).

Status is NOT carried in `ClearanceRegistered`'s payload -- the event
type IS the state-change indicator (matches `CapabilityDefined ->
DEFINED`, `SubjectMounted -> MOUNTED`, `SupplyRegistered -> UNKNOWN`).

`bindings`, `declarations`, `risk_band` travel in the genesis payload
as primitive-encoded structures (see `serialize_bindings` and
`serialize_declarations` for the JSON shape). The evolver reconstructs
typed VOs.

`kind` and `risk_band` travel as primitive strings (StrEnum values);
the evolver reconstructs via `ClearanceKind(payload["kind"])` and
`RiskBand(payload["risk_band"]) if payload.get("risk_band") else None`.

The 4 typed ClearanceBinding arms (Subject / Asset / Run / Procedure)
encode as `{"kind": "Subject", "id": "<uuid>"}` etc.; ExternalBinding
encodes as `{"kind": "External", "scheme": "...", "id": "..."}`. The
evolver dispatches on the `"kind"` discriminator. Same shape pattern as
ClearanceBinding's typed-arm-vs-ExternalBinding split is preserved on
the wire.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.safety.aggregates.clearance.state import (
    AssetBinding,
    ClearanceBinding,
    ExternalBinding,
    HazardDeclaration,
    ProcedureBinding,
    RunBinding,
    SubjectBinding,
)
from cora.safety.hazard_classification import (
    GHSPictogram,
    HazardClassification,
    NFPA704Rating,
    RiskBand,
    SchemeCode,
)


@dataclass(frozen=True)
class ClearanceRegistered:
    """A new safety-form clearance was registered.

    Status is implicit (`Defined`) -- the evolver sets it. Per the
    cross-aggregate genesis-event convention, the event type IS the
    state-change indicator.

    Carries the full Clearance shape at registration time:
    `kind / title / bindings / declarations / risk_band /
    external_id? / valid_from? / valid_until? / parent_clearance_id?`.

    `parent_clearance_id` is non-None only for Clearances registered
    via the future `amend_clearance` slice (11a-c). For 11a-a's
    `register_clearance`, parent_clearance_id is always None.
    """

    clearance_id: UUID
    kind: str
    facility_asset_id: UUID
    title: str
    bindings: tuple[dict[str, Any], ...]
    declarations: tuple[dict[str, Any], ...]
    risk_band: str | None
    external_id: str | None
    valid_from: datetime | None
    valid_until: datetime | None
    parent_clearance_id: UUID | None
    occurred_at: datetime


# Discriminated union of every event the Clearance aggregate emits.
# Phase 11a-a: just ClearanceRegistered. Phase 11a-b/c add the 9 FSM events.
ClearanceEvent = ClearanceRegistered


def event_type_name(event: ClearanceEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


# ---------------------------------------------------------------------------
# Serialization helpers (binding / classification primitives <-> typed VOs)
#
# Public (no leading underscore) because the route layer + decider also use
# these to bridge wire shape <-> typed VOs. Dropping the underscore signals
# that they are the sanctioned cross-slice helpers, not aggregate-private.
# ---------------------------------------------------------------------------


def serialize_binding(binding: ClearanceBinding) -> dict[str, Any]:
    """Encode a typed ClearanceBinding to a JSON-friendly dict.

    The dict carries a `"kind"` discriminator plus the binding-specific
    fields (id for typed-arm refs; scheme + id for ExternalBinding).
    """
    match binding:
        case SubjectBinding(subject_id=subject_id):
            return {"kind": "Subject", "id": str(subject_id)}
        case AssetBinding(asset_id=asset_id):
            return {"kind": "Asset", "id": str(asset_id)}
        case RunBinding(run_id=run_id):
            return {"kind": "Run", "id": str(run_id)}
        case ProcedureBinding(procedure_id=procedure_id):
            return {"kind": "Procedure", "id": str(procedure_id)}
        case ExternalBinding(scheme=scheme, id=id_):
            return {"kind": "External", "scheme": scheme, "id": id_}
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(binding)


def deserialize_binding(payload: dict[str, Any]) -> ClearanceBinding:
    """Decode a JSON-friendly dict to a typed ClearanceBinding.

    Dispatches on `payload["kind"]`; raises ValueError on any
    discriminator-or-inner-field violation so a contaminated event
    payload fails loud (KeyError + TypeError are wrapped to ValueError
    so callers don't see leaked low-level exceptions).
    """
    try:
        kind = payload["kind"]
        match kind:
            case "Subject":
                return SubjectBinding(subject_id=UUID(payload["id"]))
            case "Asset":
                return AssetBinding(asset_id=UUID(payload["id"]))
            case "Run":
                return RunBinding(run_id=UUID(payload["id"]))
            case "Procedure":
                return ProcedureBinding(procedure_id=UUID(payload["id"]))
            case "External":
                return ExternalBinding(scheme=payload["scheme"], id=payload["id"])
            case _:
                msg = f"Unknown ClearanceBinding kind: {kind!r}"
                raise ValueError(msg)
    except (KeyError, TypeError, AttributeError) as exc:
        msg = f"Malformed ClearanceBinding payload {payload!r}: {exc}"
        raise ValueError(msg) from exc


def serialize_classification(c: HazardClassification) -> dict[str, Any]:
    """Encode a typed HazardClassification to a JSON-friendly dict.

    Discriminator `"kind"` selects the arm:
      - `NFPA704`  -- carries health/flammability/instability/special
      - `RiskBand` -- carries band string
      - `GHS`      -- carries pictogram code + sorted statement_codes list
      - `Scheme`   -- carries scheme/code/severity_label
    """
    match c:
        case NFPA704Rating(
            health=health,
            flammability=flammability,
            instability=instability,
            special=special,
        ):
            return {
                "kind": "NFPA704",
                "health": health,
                "flammability": flammability,
                "instability": instability,
                "special": special,
            }
        case RiskBand():
            return {"kind": "RiskBand", "band": c.value}
        case GHSPictogram(code=code, statement_codes=statement_codes):
            return {
                "kind": "GHS",
                "code": code,
                "statement_codes": sorted(statement_codes),
            }
        case SchemeCode(scheme=scheme, code=code, severity_label=severity_label):
            return {
                "kind": "Scheme",
                "scheme": scheme,
                "code": code,
                "severity_label": severity_label,
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(c)


def deserialize_classification(payload: dict[str, Any]) -> HazardClassification:
    """Decode a JSON-friendly dict to a typed HazardClassification.

    Same defensive contract as `deserialize_binding`: any inner-field
    access failure (missing key, wrong type, invalid enum value, etc.)
    is re-raised as ValueError so a contaminated stream fails loud.
    """
    try:
        kind = payload["kind"]
        match kind:
            case "NFPA704":
                return NFPA704Rating(
                    health=payload["health"],
                    flammability=payload["flammability"],
                    instability=payload["instability"],
                    special=payload.get("special"),
                )
            case "RiskBand":
                return RiskBand(payload["band"])
            case "GHS":
                return GHSPictogram(
                    code=payload["code"],
                    statement_codes=frozenset(payload.get("statement_codes", [])),
                )
            case "Scheme":
                return SchemeCode(
                    scheme=payload["scheme"],
                    code=payload["code"],
                    severity_label=payload.get("severity_label", ""),
                )
            case _:
                msg = f"Unknown HazardClassification kind: {kind!r}"
                raise ValueError(msg)
    except (KeyError, TypeError, AttributeError) as exc:
        msg = f"Malformed HazardClassification payload {payload!r}: {exc}"
        raise ValueError(msg) from exc


def serialize_declaration(d: HazardDeclaration) -> dict[str, Any]:
    """Encode a HazardDeclaration to a JSON-friendly dict."""
    return {
        "target": serialize_binding(d.target),
        "classifications": [serialize_classification(c) for c in d.classifications],
        "mitigations": sorted(d.mitigations),
        "notes": d.notes,
    }


def deserialize_declaration(payload: dict[str, Any]) -> HazardDeclaration:
    """Decode a JSON-friendly dict to a HazardDeclaration.

    Defensive: KeyError / TypeError on inner fields are wrapped to
    ValueError so a contaminated stream fails loud at the evolver.
    """
    try:
        return HazardDeclaration(
            target=deserialize_binding(payload["target"]),
            classifications=frozenset(
                deserialize_classification(c) for c in payload.get("classifications", [])
            ),
            mitigations=frozenset(payload.get("mitigations", [])),
            notes=payload.get("notes"),
        )
    except (KeyError, TypeError, AttributeError) as exc:
        msg = f"Malformed HazardDeclaration payload {payload!r}: {exc}"
        raise ValueError(msg) from exc


def to_payload(event: ClearanceEvent) -> dict[str, Any]:
    """Serialize a Clearance event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings, frozensets/tuples become lists. Enum values travel as
    their string values.
    """
    match event:
        case ClearanceRegistered(
            clearance_id=clearance_id,
            kind=kind,
            facility_asset_id=facility_asset_id,
            title=title,
            bindings=bindings,
            declarations=declarations,
            risk_band=risk_band,
            external_id=external_id,
            valid_from=valid_from,
            valid_until=valid_until,
            parent_clearance_id=parent_clearance_id,
            occurred_at=occurred_at,
        ):
            return {
                "clearance_id": str(clearance_id),
                "kind": kind,
                "facility_asset_id": str(facility_asset_id),
                "title": title,
                "bindings": list(bindings),
                "declarations": list(declarations),
                "risk_band": risk_band,
                "external_id": external_id,
                "valid_from": valid_from.isoformat() if valid_from is not None else None,
                "valid_until": valid_until.isoformat() if valid_until is not None else None,
                "parent_clearance_id": (
                    str(parent_clearance_id) if parent_clearance_id is not None else None
                ),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> ClearanceEvent:
    """Rebuild a Clearance event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "ClearanceRegistered":
            raw_valid_from = payload.get("valid_from")
            raw_valid_until = payload.get("valid_until")
            raw_parent = payload.get("parent_clearance_id")
            return ClearanceRegistered(
                clearance_id=UUID(payload["clearance_id"]),
                kind=payload["kind"],
                facility_asset_id=UUID(payload["facility_asset_id"]),
                title=payload["title"],
                bindings=tuple(payload.get("bindings", [])),
                declarations=tuple(payload.get("declarations", [])),
                risk_band=payload.get("risk_band"),
                external_id=payload.get("external_id"),
                valid_from=(
                    datetime.fromisoformat(raw_valid_from) if raw_valid_from is not None else None
                ),
                valid_until=(
                    datetime.fromisoformat(raw_valid_until) if raw_valid_until is not None else None
                ),
                parent_clearance_id=(UUID(raw_parent) if raw_parent is not None else None),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown ClearanceEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "ClearanceEvent",
    "ClearanceRegistered",
    "deserialize_binding",
    "deserialize_classification",
    "deserialize_declaration",
    "event_type_name",
    "from_stored",
    "serialize_binding",
    "serialize_classification",
    "serialize_declaration",
    "to_payload",
]
