-- Post-6g audit naming cleanup: rename projection columns to match
-- the natural-English `default_parameters` / `override_parameters`
-- field renames (was `parameter_defaults` / `parameter_overrides`).
--
-- Why rename: the original `parameter_*` shape (singular adjective +
-- plural role-noun) read awkwardly in English ("parameter defaults"
-- as adjectival construction). The natural form swaps to
-- `<role>_parameters` for consistency with `effective_parameters`.
-- See [[project_naming_conventions]] for the lessons documented in
-- the post-rename memo.
--
-- Greenfield-safe: no production data; columns are projection-side
-- (regenerable from event stream). The CI safety scan blocks
-- `DROP COLUMN`, but `RENAME COLUMN` is allowed (data preserved
-- in place).

-- atlas:safety:allow=rename-column-allowed-data-preserving

ALTER TABLE proj_recipe_plan_summary
    RENAME COLUMN parameter_defaults_present TO default_parameters_present;

ALTER TABLE proj_run_summary
    RENAME COLUMN parameter_overrides_present TO override_parameters_present;
