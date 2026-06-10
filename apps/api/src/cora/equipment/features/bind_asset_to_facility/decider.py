"""Pure decider for the `BindAssetToFacility` command.

Pure function: given the current Asset state, a `BindAssetToFacility`
command, and the cross-BC `FacilityLookupResult | None` loaded by the
handler, returns the events to append. No I/O, no awaits, no side
effects.

## Invariants

  - Asset must exist (state non-None) -> `AssetNotFoundError`
  - Asset.facility_code must currently be None
    -> `AssetFacilityCodeAlreadyAssignedError` (set-once per
    [[project-slice8-design]] L2; rebind path is decommission +
    re-register)
  - `facility_lookup_result` must be non-None (Facility must exist
    in the Federation projection) -> `AssetFacilityNotFoundError`

## Source-of-truth

The lookup result's `.code` field is folded onto the emitted event,
NOT a command-echo. Mirrors the Supply Slice 7A handler/decider
split: the projection's canonical FacilityCode wins over whatever
the operator typed (case-normalization happens at the
FacilityLookup adapter, not here).

## Decommissioned-Facility binding is ALLOWED

Mirrors the register_asset 8A `AssetFacilityNotFoundError` precedent:
the decider does NOT partition on Facility status. Operators may
keep Decommissioned-facility lineage visible by binding Assets
against it. The lookup adapter does not filter on status.
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetFacilityCodeAlreadyAssignedError,
    AssetFacilityCodeAssigned,
    AssetFacilityNotFoundError,
    AssetNotFoundError,
)
from cora.equipment.features.bind_asset_to_facility.command import BindAssetToFacility
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.identity import ActorId


def decide(
    state: Asset | None,
    command: BindAssetToFacility,
    *,
    now: datetime,
    assigned_by: ActorId,
    facility_lookup_result: FacilityLookupResult | None,
) -> list[AssetFacilityCodeAssigned]:
    """Decide the events produced by binding an Asset to a Facility.

    The handler is responsible for loading both Asset state and
    `facility_lookup_result`; this decider is a pure function over
    its inputs.

    Invariants:
      - Asset must exist (state non-None) -> AssetNotFoundError
      - Asset.facility_code must currently be None (set-once per L2)
        -> AssetFacilityCodeAlreadyAssignedError
      - facility_lookup_result must be non-None (Facility must exist
        in the Federation projection)
        -> AssetFacilityNotFoundError
    """
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    if state.facility_code is not None:
        raise AssetFacilityCodeAlreadyAssignedError(state.id, state.facility_code)

    if facility_lookup_result is None:
        raise AssetFacilityNotFoundError(command.facility_code)

    return [
        AssetFacilityCodeAssigned(
            asset_id=state.id,
            facility_code=facility_lookup_result.code,
            occurred_at=now,
            assigned_by=assigned_by,
        )
    ]
