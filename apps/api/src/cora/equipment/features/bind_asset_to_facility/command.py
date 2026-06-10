"""The `BindAssetToFacility` command, intent dataclass for this slice.

Set-once post-genesis binding of an existing Asset to its owning
Federation Facility. Mirrors `attach_asset_to_fixture` in shape;
mirrors Asset.facility_code at register_asset (Slice 8A) in
semantics: same FacilityLookup port, same AssetFacilityNotFoundError
on unknown slugs, same Decommissioned-Facility-binding-allowed rule.

Per [[project-slice8-design]] L2: binding is set-once. The decider
raises AssetFacilityCodeAlreadyAssignedError when the target Asset
already carries a non-None facility_code (whether set at
register_asset time or at a prior bind_asset_to_facility call).
Rebind path is decommission + re-register, mirroring the
Asset.model_id Lock A precedent.

`facility_code` is bare `str` on the command (matches the
Permit / Credential / Seal wire convention of bare-str slugs on
commands + typed `FacilityCode` VO on aggregate state); the handler
wraps in `FacilityCode(...)` at the port edge before calling
`FacilityLookup.lookup_by_code`. Server-side concerns (wall-clock
timestamp, correlation id, per-event ids) are injected by the
handler from infrastructure ports.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class BindAssetToFacility:
    """Bind an existing Asset to its owning Facility (set-once)."""

    asset_id: UUID
    facility_code: str
