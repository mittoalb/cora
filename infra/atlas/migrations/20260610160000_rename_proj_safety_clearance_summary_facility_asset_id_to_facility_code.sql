-- Rename Clearance summary projection's facility column to align with the
-- cross-deployment convergent slug convention shipped across Slices 6, 7, 8:
-- `facility_asset_id UUID NOT NULL` -> `facility_code TEXT NOT NULL`.
--
-- The Clearance.facility_asset_id aggregate field and the ClearanceRegistered
-- payload key were renamed in the same step. The aggregate-level field's
-- type also flipped from UUID (Asset row id) to FacilityCode (cross-
-- deployment slug), so the projection column type changes alongside the
-- name. The new value stores the bare FacilityCode slug ("aps", "maxiv",
-- etc.) per the Slice 8A precedent on proj_equipment_asset_summary.
--
-- The USING cast preserves any existing dev/test data: UUID values cast to
-- their canonical string form, which downstream code overwrites on the
-- next register_clearance.
--
-- Forward-only per project_forward_only_migrations.md. Greenfield
-- (pre-pilot): no production rows exist, so the rename + type-flip
-- window is at its narrowest.

ALTER TABLE proj_safety_clearance_summary
    ALTER COLUMN facility_asset_id TYPE TEXT USING facility_asset_id::text;

ALTER TABLE proj_safety_clearance_summary
    RENAME COLUMN facility_asset_id TO facility_code;
