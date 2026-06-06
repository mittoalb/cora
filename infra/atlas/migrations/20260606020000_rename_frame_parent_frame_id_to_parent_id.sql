-- Rename Frame self-parent column to drop the redundant `frame_` infix:
-- `parent_frame_id` -> `parent_id` on the Frame projections.
--
-- The Frame.parent_frame_id aggregate field and the FrameRegistered
-- payload key were renamed in the same audit step; this migration
-- closes the column-level asymmetry on the two affected projections:
--
--   - proj_equipment_frame_summary.parent_frame_id  -> parent_id
--   - proj_equipment_frame_children.parent_frame_id -> parent_id
--     (composite PK column; PostgreSQL renames the PK + index transparently)
--
-- The frame_summary parent index also gets renamed for cleanliness.
--
-- proj_equipment_frame_consumers is NOT touched: its column is
-- `referenced_frame_id` (not parent_frame_id) and the consumer-type
-- discriminator already makes the role explicit.
--
-- Forward-only per project_forward_only_migrations.md. Greenfield
-- (pre-pilot): no production rows exist, so the rename window is at
-- its narrowest.

ALTER TABLE proj_equipment_frame_summary
    RENAME COLUMN parent_frame_id TO parent_id;

ALTER INDEX proj_equipment_frame_summary_parent_idx
    RENAME TO proj_equipment_frame_summary_parent_id_idx;

ALTER TABLE proj_equipment_frame_children
    RENAME COLUMN parent_frame_id TO parent_id;
