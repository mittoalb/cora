-- Rename proj_equipment_frame_summary column to match the
-- post-2026-05-31 naming audit: `placement_relative_to_parent`
-- -> `placement`. The Frame state field and the FrameRegistered
-- payload key were renamed in the same audit batch; this migration
-- closes the column-level asymmetry.
--
-- The verbose original name was defensive (Frame.placement is
-- OPTIONAL: None for root frames). The audit settled on the terser
-- name to match Mount.placement; the optionality is encoded in the
-- column being NULLable.
--
-- Forward-only per project_forward_only_migrations.md. Mount/Frame
-- Stage-1 shipped 2026-05-31; the rename window for this column is
-- at its narrowest (effectively-empty table).

ALTER TABLE proj_equipment_frame_summary
    RENAME COLUMN placement_relative_to_parent TO placement;
