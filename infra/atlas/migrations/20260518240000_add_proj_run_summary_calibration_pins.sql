-- Phase 12b-2: expose `Run.calibration_pins` on the Run BC read surface.
--
-- The Calibration BC ↔ Run BC integration at Phase 12b-1 added the
-- AsShot pin set to `Run.calibration_pins` (in-memory + event payload).
-- This migration surfaces the pinned `CalibrationRevision.id`s on the
-- `proj_run_summary` read model so downstream consumers can query
-- "which calibrations was this Run acquired against?" without folding
-- the Run stream.
--
-- Two driving consumer queries:
--   1. Phase 12c (Dataset.calibrations_used): when a reconstruction
--      Dataset wants to default-cite the producing Run's pins, it
--      reads them from this column.
--   2. The future RunDebrief / RotationCenterRefiner subscribers
--      (per [[project_calibration_design]] watch items): both need
--      to read the pin set from the read model without going
--      through the Run event stream.
--
-- Additive forward-only migration:
--   - `calibration_pins uuid[] NOT NULL DEFAULT '{}'` so legacy pre-12b
--     rows backfill cleanly to an empty array (matches the in-memory
--     frozenset default + the `from_stored` forward-compat fold of
--     pre-12b `RunStarted` payloads that lacked `calibration_pins`).
--   - GIN index supports the `WHERE $N = ANY(calibration_pins)` filter
--     pattern (mirrors the safety BC's per-binding GIN indexes); this
--     lights up the "show me every Run that pinned CalibrationRevision X"
--     query path that 12c's Dataset back-fill + agent-subscriber
--     replay will both want.
--
-- Projection's `apply()` for `RunStarted` is updated in the same commit
-- (`cora.run.projections.summary._INSERT_RUN_SQL`) to write
-- `calibration_pins = payload.get("calibration_pins", [])`.

ALTER TABLE proj_run_summary
    ADD COLUMN calibration_pins UUID[] NOT NULL DEFAULT '{}';

CREATE INDEX proj_run_summary_calibration_pins_gin_idx
    ON proj_run_summary USING GIN (calibration_pins);
