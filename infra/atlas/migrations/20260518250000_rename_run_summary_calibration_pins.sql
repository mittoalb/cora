-- Phase 12b-4: rename `Run.calibration_pins` -> `Run.pinned_calibrations`
-- to align with the [[project-naming-conventions]] R3 family-noun-LAST
-- convention and stay symmetric with the upcoming Phase 12c
-- `Dataset.used_calibrations`. The rename is mechanical: column +
-- index name only; column type, NOT NULL, DEFAULT, and constraint
-- semantics are identical to the pre-12b-4 shape.
--
-- Forward-only per [[project-forward-only-migrations]]. The prior
-- migration `20260518240000_add_proj_run_summary_calibration_pins`
-- stays in history unchanged; this commit's source-tree rename in
-- the Run BC (state.py, events.py, evolver.py, command/decider/route/
-- tool/projection) lands in lockstep so the projection writer + the
-- query path both use the new column name from cutover.
--
-- Atlas `RENAME COLUMN` issues `ALTER TABLE ... RENAME COLUMN`
-- (instantaneous metadata-only DDL; no row rewrite, no AccessExclusive
-- on data). `RENAME INDEX` is also metadata-only.

ALTER TABLE proj_run_summary
    RENAME COLUMN calibration_pins TO pinned_calibrations;

ALTER INDEX proj_run_summary_calibration_pins_gin_idx
    RENAME TO proj_run_summary_pinned_calibrations_gin_idx;
