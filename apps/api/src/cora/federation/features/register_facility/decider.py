"""Pure decider for the `RegisterFacility` command.

Pure function: given the (always None) Facility state and a
`RegisterFacility` command, returns the events to append on the
Facility stream. No I/O, no awaits, no side effects.

`now`, `code`, `display_name`, and `registered_by` are constructed
by the application handler at the port edge (FacilityCode + FacilityName
VO construction enforces field-shape invariants and surfaces
`InvalidFacilityCodeError` + `InvalidFacilityNameError` at the route
boundary as 422). The decider receives already-validated VOs.

The Facility id is derived deterministically by the handler from
`FacilityCode.value` via `facility_stream_id` (UUID5 over a frozen
namespace); the decider receives the derived id and uses it verbatim
in the genesis event.

Invariants enforced by this decider (belt-and-braces with the Facility
dataclass `__post_init__`):
  - State must be None (genesis-only)
    -> FacilityAlreadyExistsError
  - kind=Site implies parent_id is None
    -> FacilitySiteCannotHaveParentError
  - kind=Area implies parent_id is non-None
    -> FacilityAreaMustHaveParentError

Cross-stream invariants NOT enforced here (deferred to slice 6 with
the FacilityLookup port surface):
  - parent_id, if non-None, must reference an existing Facility row
    whose kind is Site.

`code`, `display_name`, `kind`, and `alternate_identifiers` are
validated at the Pydantic + VO boundary (route / tool); the decider
trusts the typed inputs.
"""

from datetime import datetime

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.aggregates.facility import (
    Facility,
    FacilityAlreadyExistsError,
    FacilityAreaMustHaveParentError,
    FacilityKind,
    FacilityRegistered,
    FacilitySiteCannotHaveParentError,
)
from cora.federation.features.register_facility.command import RegisterFacility
from cora.infrastructure.facility_code import FacilityCode
from cora.infrastructure.identity import ActorId


def decide(
    state: Facility | None,
    command: RegisterFacility,
    *,
    now: datetime,
    facility_id: FacilityId,
    code: FacilityCode,
    registered_by: ActorId,
) -> list[FacilityRegistered]:
    """Decide the events produced by registering a new Facility.

    Invariants:
      - State must be None (genesis-only) -> FacilityAlreadyExistsError
      - kind=Site + parent_id is not None -> FacilitySiteCannotHaveParentError
      - kind=Area + parent_id is None     -> FacilityAreaMustHaveParentError
    """
    if state is not None:
        raise FacilityAlreadyExistsError(state.code)

    if command.kind is FacilityKind.SITE and command.parent_id is not None:
        raise FacilitySiteCannotHaveParentError(code, command.parent_id)

    if command.kind is FacilityKind.AREA and command.parent_id is None:
        raise FacilityAreaMustHaveParentError(code)

    return [
        FacilityRegistered(
            facility_id=facility_id,
            code=code,
            display_name=command.display_name,
            kind=command.kind,
            parent_id=command.parent_id,
            registered_by=registered_by,
            occurred_at=now,
            alternate_identifiers=command.alternate_identifiers,
        )
    ]


__all__ = ["decide"]
