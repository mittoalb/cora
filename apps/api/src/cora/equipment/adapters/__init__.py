"""Equipment BC adapters.

`StubDoiMinter` is the test-tier `DoiMinter` adapter per
[[project-asset-persistent-id-write-design]] (slice F.1): a real
adapter that returns inert deterministic values, distinct from a
None / disabled port. Mirrors `AllowAllAuthorize` and
`AlwaysCoveredClearanceLookup` test-bypass convention. The
production `DataCiteDoiMinter` adapter is deferred to slice F.2.

`PostgresAssetLookup` is the production `AssetLookup` adapter per
Session 5 Slice 7B (cross-BC Supply.containing_asset_id binding +
future Slice 8 Asset.facility_id binding). Reads
`proj_equipment_asset_summary`; the test-tier `InMemoryAssetLookup`
lives at `cora.infrastructure.adapters` mirroring the
`FacilityLookup` split.

`PostgresRoleLookup` is the production `RoleLookup` adapter per
Layer 3 sub-slice 3A of [[project-role-aggregate-design]]. Reads
`proj_equipment_role_summary`; the test-tier `InMemoryRoleLookup`
lives at `cora.infrastructure.adapters` mirroring the
`AssetLookup` / `FacilityLookup` split.
"""

from cora.equipment.adapters.postgres_asset_lookup import PostgresAssetLookup
from cora.equipment.adapters.postgres_role_lookup import PostgresRoleLookup

__all__ = ["PostgresAssetLookup", "PostgresRoleLookup"]
