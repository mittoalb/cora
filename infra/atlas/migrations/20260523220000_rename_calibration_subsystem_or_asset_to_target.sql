-- D16 from the 2026-05-22 cross-package consistency audit: rename the
-- Calibration projection's `subsystem_or_asset_id` column to `target_id`.
-- The design memo `project_calibration_design` deliberately allowed
-- non-Asset targets ("typically Asset.id" qualifier) so `target_id` is
-- the right name; the compound "subsystem_or_asset" form violates the
-- family-noun-primacy naming rule.
--
-- Same rename happens at the aggregate/event/handler/test layers in
-- the source tree; this migration brings the projection column + the
-- two indexes that named the old column in their own names.
--
-- Forward-only per [[project_forward_only_migrations]]. Idempotent via
-- IF EXISTS; one ALTER per object so a partial apply leaves the
-- projection in a consistent state.

ALTER TABLE proj_calibration_summary
    RENAME COLUMN subsystem_or_asset_id TO target_id;

-- Index renames: the underlying column reference auto-updates inside
-- the index definition, but the index name itself still carries the
-- old "scope_idx" / "verified_idx" terms tied to the old vocabulary.
-- Rename so operators grepping pg_indexes find the new terms.
ALTER INDEX IF EXISTS proj_calibration_summary_scope_idx
    RENAME TO proj_calibration_summary_target_quantity_idx;

ALTER INDEX IF EXISTS proj_calibration_summary_verified_idx
    RENAME TO proj_calibration_summary_target_quantity_verified_idx;
