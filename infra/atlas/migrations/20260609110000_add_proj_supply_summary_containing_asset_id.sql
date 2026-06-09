-- Session 5 Slice 7B: cross-BC containing-Asset binding on Supply.
--
-- Adds the `containing_asset_id` column to `proj_supply_summary` so
-- the Supply BC's read model carries the optional physical-equipment
-- containment back-reference per
-- [[project_supply_sector_disposition]] Option A (the former
-- `SupplyScope.Sector` + `SupplyScope.Beamline` enum values collapse
-- to relational references to the Equipment BC's Asset hierarchy).
-- The `register_supply` slice's projection writer (apps/api/src/cora/
-- supply/projections/supply.py) populates this column on every
-- `SupplyRegistered` event going forward; `None` (NULL) semantically
-- means "facility-scope resource" (paired with non-NULL
-- `facility_code`).
--
-- The column is nullable in this slice because most Supplies will be
-- facility-scope (NULL) and the field is OPTIONAL on registration per
-- the Option A disposition. Forward-only per
-- [[project_forward_only_migrations]]: no DROP, no rollback. Slice 7C
-- will swap the UNIQUE INDEX to compose `containing_asset_id` into the
-- (kind, name) uniqueness tuple via COALESCE so that NULL
-- containing-Asset rows are still subject to per-facility uniqueness.
-- Slice 7C also adds a non-unique index for the
-- `?containing_asset_id=` operator filter that Slice 7D introduces.

ALTER TABLE proj_supply_summary
    ADD COLUMN containing_asset_id UUID NULL;
