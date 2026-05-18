-- Phase 5i: rename today's Equipment BC `Capability` aggregate to `Family`.
--
-- Per DLM-A [[family-affordance-design-phases-5i-5j-lock]], this is a
-- direct rename (Marten/Axon canonical pattern). The projection table
-- and column are renamed for clarity; the projection_bookmarks row is
-- UPDATEd (not re-inserted) so the cursor position is preserved.
--
-- Event-store stream_type is unified to "Family" in the new code path
-- (see `apps/api/src/cora/equipment/aggregates/family/read.py`). CORA
-- is greenfield at 5i lock time, so no `events.stream_type` migration
-- ships here. Any future deployment carrying historical streams under
-- the old `"Capability"` stream_type would need a one-time forward
-- migration that updates BOTH `events.stream_type` (Capability →
-- Family) AND `events.event_type` (Capability* → Family*) plus the
-- `payload` key (capability_id → family_id) so projections rebuild
-- correctly. Event-payload IMMUTABILITY at the row level is preserved
-- per [[project_immutability_guarantee]] — only the categorization
-- labels would change. Watch item documented in DLM-A.
--
-- Greenfield-safe: no production data; projections are regenerable
-- from event stream because the `FamilySummaryProjection` subscribes
-- to BOTH legacy `Capability*` event types AND new `Family*` types
-- (per the Marten/Axon dual-match contract from DLM-A). CI rename-
-- column allow needed for the column + table + index renames below.

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
