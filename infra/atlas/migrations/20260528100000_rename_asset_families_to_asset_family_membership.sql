-- Rename the asset<->family join projection to use an explicit
-- per-row noun (`membership`), bringing it in line with the
-- `proj_<bc>_<base>_<rowtype>` naming convention the sibling
-- summary projections already follow (`proj_equipment_asset_summary`,
-- `proj_equipment_family_summary`: per-row noun = `summary`).
--
-- Before: proj_equipment_asset_families            (plural, ambiguous
--                                                   per-row noun)
-- After:  proj_equipment_asset_family_membership   (singular per row
--                                                   = one membership)
--
-- The bookmark name in `projection_bookmarks` is also renamed so the
-- projection class's `name` attribute matches; without that, the
-- worker would re-fold the entire history on first run after the
-- rename (writing duplicate rows that ON CONFLICT DO NOTHING would
-- absorb, but the bookmark drift would persist).
--
-- Forward-only: simple ALTER RENAME for table, index, and bookmark
-- row. No data movement, no downtime.

ALTER TABLE proj_equipment_asset_families
    RENAME TO proj_equipment_asset_family_membership;

ALTER INDEX proj_equipment_asset_families_by_family_idx
    RENAME TO proj_equipment_asset_family_membership_by_family_idx;

UPDATE projection_bookmarks
    SET name = 'proj_equipment_asset_family_membership'
    WHERE name = 'proj_equipment_asset_families';
