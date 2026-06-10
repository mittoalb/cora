-- Slice 8A: add the Asset.facility_code cross-BC binding column to
-- the equipment asset projection, mirroring Supply Slice 7A
-- (`add_proj_supply_summary_facility_code`).
--
-- `facility_code` is the cross-deployment convergent slug
-- (Federation BC `FacilityCode`) of the Facility owning this Asset.
-- Per [[project-slice8-design]] L1 + L7, the column is nullable
-- because Asset.facility_code is OPTIONAL day-one (additive
-- forward-compat: legacy rows registered before Slice 8 stay NULL).
-- The Slice 8C lifespan-hook backfill populates rows for existing
-- Site / Area level Assets in a subsequent migration window.
--
-- ## Column shape
--
-- TEXT NULL matches the FacilityCode regex contract
-- ([a-z0-9-]{1,32}) without a CHECK because (a) the aggregate VO
-- enforces the regex at write time, (b) cross-deployment alignment
-- relies on byte-identical slugs but never on database-tier
-- enforcement, (c) the Slice 7A precedent on proj_supply_summary
-- also omits the CHECK for the same reasons.
--
-- ## Non-unique partial index
--
-- B-tree on facility_code, PARTIAL on WHERE facility_code IS NOT
-- NULL. Backs the per-facility list filter (the get/list responses
-- surface facility_code, and a future `?facility_code=` query
-- parameter on `GET /assets` consumes the index for predicate
-- pushdown). Partial index keeps the bytes narrow because the
-- column is NULL for most rows today.
--
-- NO UNIQUE INDEX migration: proj_equipment_asset_summary has
-- ZERO uniqueness invariant on Asset name today (only PRIMARY KEY
-- on asset_id), so the Slice 7C precedent of swapping
-- `(scope, kind, name)` to `(facility_code, COALESCE(...), kind,
-- name)` does NOT apply here. Future Asset name-uniqueness
-- proposals would be a separate slice.
--
-- ## Forward-only
--
-- Pure ADD COLUMN + ADD INDEX; greenfield-friendly; no backfill
-- inside this migration (Slice 8C lifespan hook handles the
-- backfill via the register_facility command bus, which keeps the
-- Federation aggregate as the source of truth).

ALTER TABLE proj_equipment_asset_summary
    ADD COLUMN facility_code TEXT;

CREATE INDEX proj_equipment_asset_summary_facility_code_idx
    ON proj_equipment_asset_summary (facility_code)
    WHERE facility_code IS NOT NULL;
