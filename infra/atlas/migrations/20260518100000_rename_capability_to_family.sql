-- Phase 5i: rename today's Equipment BC `Capability` aggregate to `Family`.
--
-- Per DLM-A [[family-affordance-design-phases-5i-5j-lock]], this is a
-- direct rename (Marten/Axon canonical pattern): the storage labels
-- change to match the new aggregate name; the underlying event-store
-- stream type stays "Capability" (rename residual; see
-- `equipment/aggregates/family/read.py` docstring) because that's an
-- internal categorization string. Projection tables and columns DO
-- rename for clarity.
--
-- Greenfield-safe: no production data; projections are regenerable
-- from event stream. CI rename-column allow needed.

-- atlas:safety:allow=rename-column-allowed-data-preserving

-- 1. Rename Family summary projection table + its capability_id column.
ALTER TABLE proj_equipment_capability_summary
    RENAME TO proj_equipment_family_summary;

ALTER TABLE proj_equipment_family_summary
    RENAME COLUMN capability_id TO family_id;

ALTER INDEX proj_equipment_capability_summary_keyset_idx
    RENAME TO proj_equipment_family_summary_keyset_idx;

-- 2. Update the projection_bookmarks entry from the old name to the new.
--    Use UPDATE so the bookmark cursor position is preserved across the
--    rename (avoids re-replay of all historical events).
UPDATE projection_bookmarks
    SET name = 'proj_equipment_family_summary'
    WHERE name = 'proj_equipment_capability_summary';
