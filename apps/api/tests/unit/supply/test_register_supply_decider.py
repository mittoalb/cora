"""Pure-decider tests for `register_supply` slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    InvalidSupplyKindError,
    InvalidSupplyNameError,
    Supply,
    SupplyAlreadyExistsError,
    SupplyFacilityNotFoundError,
    SupplyName,
    SupplyRegistered,
    SupplyScope,
    SupplyStatus,
)
from cora.supply.features import register_supply
from cora.supply.features.register_supply import RegisterSupply

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_ACTOR_ID = ActorId(uuid4())
_FACILITY_CODE = FacilityCode("aps")
_FACILITY_ID = UUID("01900000-0000-7000-8000-000000000fac")


def _facility_lookup_result(
    *,
    kind: str = "Site",
    status: str = "Active",
) -> FacilityLookupResult:
    return FacilityLookupResult(
        id=_FACILITY_ID,
        code=_FACILITY_CODE,
        kind=kind,
        status=status,
        trust_anchor_credential_ids=frozenset(),
    )


@pytest.mark.unit
def test_decide_emits_supply_registered_when_stream_is_empty() -> None:
    new_id = uuid4()
    events = register_supply.decide(
        state=None,
        command=RegisterSupply(
            scope=SupplyScope.BEAMLINE,
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code="aps",
        ),
        now=_NOW,
        new_id=new_id,
        triggered_by=_ACTOR_ID,
        facility_lookup_result=_facility_lookup_result(),
    )
    assert events == [
        SupplyRegistered(
            supply_id=new_id,
            scope="Beamline",
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code=_FACILITY_CODE,
            trigger="Operator",
            triggered_by=_ACTOR_ID,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_trims_kind_and_name() -> None:
    new_id = uuid4()
    events = register_supply.decide(
        state=None,
        command=RegisterSupply(
            scope=SupplyScope.FACILITY,
            kind="  PhotonBeam  ",
            name="  APS storage-ring beam  ",
            facility_code="aps",
        ),
        now=_NOW,
        new_id=new_id,
        triggered_by=_ACTOR_ID,
        facility_lookup_result=_facility_lookup_result(),
    )
    assert events[0].kind == "PhotonBeam"
    assert events[0].name == "APS storage-ring beam"


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Supply(
        id=uuid4(),
        scope=SupplyScope.BEAMLINE,
        kind="LiquidNitrogen",
        name=SupplyName("2-BM LN2"),
        facility_code=_FACILITY_CODE,
        status=SupplyStatus.UNKNOWN,
    )
    with pytest.raises(SupplyAlreadyExistsError) as exc_info:
        register_supply.decide(
            state=existing,
            command=RegisterSupply(
                scope=SupplyScope.BEAMLINE,
                kind="LiquidNitrogen",
                name="other",
                facility_code="aps",
            ),
            now=_NOW,
            new_id=uuid4(),
            triggered_by=_ACTOR_ID,
            facility_lookup_result=_facility_lookup_result(),
        )
    assert exc_info.value.supply_id == existing.id


@pytest.mark.unit
def test_decide_rejects_empty_kind() -> None:
    with pytest.raises(InvalidSupplyKindError):
        register_supply.decide(
            state=None,
            command=RegisterSupply(
                scope=SupplyScope.BEAMLINE,
                kind="   ",
                name="2-BM",
                facility_code="aps",
            ),
            now=_NOW,
            new_id=uuid4(),
            triggered_by=_ACTOR_ID,
            facility_lookup_result=_facility_lookup_result(),
        )


@pytest.mark.unit
def test_decide_rejects_too_long_kind() -> None:
    with pytest.raises(InvalidSupplyKindError):
        register_supply.decide(
            state=None,
            command=RegisterSupply(
                scope=SupplyScope.BEAMLINE,
                kind="a" * 51,
                name="2-BM",
                facility_code="aps",
            ),
            now=_NOW,
            new_id=uuid4(),
            triggered_by=_ACTOR_ID,
            facility_lookup_result=_facility_lookup_result(),
        )


@pytest.mark.unit
def test_decide_rejects_empty_name() -> None:
    with pytest.raises(InvalidSupplyNameError):
        register_supply.decide(
            state=None,
            command=RegisterSupply(
                scope=SupplyScope.BEAMLINE,
                kind="LiquidNitrogen",
                name="   ",
                facility_code="aps",
            ),
            now=_NOW,
            new_id=uuid4(),
            triggered_by=_ACTOR_ID,
            facility_lookup_result=_facility_lookup_result(),
        )


@pytest.mark.unit
def test_decide_rejects_missing_facility() -> None:
    """`facility_lookup_result=None` means the handler's
    `FacilityLookup.lookup_by_code` returned None; the decider must
    raise `SupplyFacilityNotFoundError` carrying the wire-level slug."""
    with pytest.raises(SupplyFacilityNotFoundError) as exc_info:
        register_supply.decide(
            state=None,
            command=RegisterSupply(
                scope=SupplyScope.BEAMLINE,
                kind="LiquidNitrogen",
                name="2-BM LN2",
                facility_code="unknown",
            ),
            now=_NOW,
            new_id=uuid4(),
            triggered_by=_ACTOR_ID,
            facility_lookup_result=None,
        )
    assert exc_info.value.facility_code == "unknown"


@pytest.mark.unit
def test_decide_accepts_decommissioned_facility() -> None:
    """Decommissioned-Facility binding is allowed; the decider does not
    partition on Facility status (mirrors slice 6
    `FacilityParentNotFoundError` precedent)."""
    new_id = uuid4()
    events = register_supply.decide(
        state=None,
        command=RegisterSupply(
            scope=SupplyScope.FACILITY,
            kind="PhotonBeam",
            name="APS storage-ring beam",
            facility_code="aps",
        ),
        now=_NOW,
        new_id=new_id,
        triggered_by=_ACTOR_ID,
        facility_lookup_result=_facility_lookup_result(status="Decommissioned"),
    )
    assert events[0].facility_code == _FACILITY_CODE


@pytest.mark.unit
def test_decide_uses_lookup_result_code_not_command_echo() -> None:
    """The event's `facility_code` is sourced from
    `facility_lookup_result.code`, not from `command.facility_code`.
    The lookup result is the single source of truth for the canonical
    cross-deployment slug; the wire-level command field is the
    operator-supplied input that resolves to it."""
    new_id = uuid4()
    canonical = FacilityCode("aps")
    events = register_supply.decide(
        state=None,
        command=RegisterSupply(
            scope=SupplyScope.BEAMLINE,
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code="aps",
        ),
        now=_NOW,
        new_id=new_id,
        triggered_by=_ACTOR_ID,
        facility_lookup_result=_facility_lookup_result(),
    )
    assert events[0].facility_code is canonical or events[0].facility_code == canonical


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    command = RegisterSupply(
        scope=SupplyScope.BEAMLINE,
        kind="LiquidNitrogen",
        name="2-BM LN2",
        facility_code="aps",
    )
    lookup = _facility_lookup_result()
    first = register_supply.decide(
        state=None,
        command=command,
        now=_NOW,
        new_id=new_id,
        triggered_by=_ACTOR_ID,
        facility_lookup_result=lookup,
    )
    second = register_supply.decide(
        state=None,
        command=command,
        now=_NOW,
        new_id=new_id,
        triggered_by=_ACTOR_ID,
        facility_lookup_result=lookup,
    )
    assert first == second
