-- Rename the Model summary projection's `declared_families` column
-- to `declared_family_ids`, bringing it in line with the UUID-
-- collection `_ids` suffix convention every other foreign-key
-- collection field in the codebase follows
-- (Method.needed_family_ids, Permit.allowed_credential_ids,
-- Asset.family_ids, etc.).
--
-- Before: declared_families      JSONB NOT NULL
-- After:  declared_family_ids    JSONB NOT NULL
--
-- The shape (JSONB array of UUID strings) is unchanged; the column
-- rename is purely lexical. The matching Model aggregate state field
-- and event payload key rename in the same commit; this migration
-- keeps the projection writer in sync.
--
-- Forward-only: simple ALTER RENAME COLUMN. No data movement, no
-- downtime. Mirrors the column-rename precedents
-- (20260514030000_rename_parameter_columns_to_default_override,
-- 20260518250000_rename_run_summary_calibration_pins).

ALTER TABLE proj_equipment_model_summary
    RENAME COLUMN declared_families TO declared_family_ids;
