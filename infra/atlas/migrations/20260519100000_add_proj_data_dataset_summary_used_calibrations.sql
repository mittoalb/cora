-- Phase 12c-2: expose `Dataset.used_calibrations` on the Data BC read surface.
--
-- The Calibration BC ↔ Data BC integration at Phase 12c-1 added the
-- AsShot citation set to `Dataset.used_calibrations` (in-memory +
-- event payload). This migration surfaces those `CalibrationRevision.id`s
-- on the `proj_data_dataset_summary` read model so downstream consumers
-- can query "which calibration revisions did this reconstruction
-- actually cite?" without folding the Dataset stream.
--
-- Symmetric to Phase 12b-2's column on `proj_run_summary`:
--   - 12b-2: `proj_run_summary.pinned_calibrations` (AsShot anchor at
--     acquisition; pinned at start_run, immutable)
--   - 12c-2: `proj_data_dataset_summary.used_calibrations` (AsShot
--     citation on derivative; pinned at register_dataset, immutable)
--
-- The two sets are independent at the DOMAIN level (revision-cited
-- atomic-ID model per [[project_calibration_design]] anti-hook #3 +
-- canonical DDD eventual-consistency stance) — a reconstruction may
-- legitimately cite refined revisions not in the producing Run's pin
-- set. NO cross-table integrity constraint here; observable drift
-- between the two columns is surfaced via the deferred projection-
-- level integrity check (Watch item #7) when consumer pain emerges.
--
-- Driving consumer queries:
--   1. Future RotationCenterRefiner / RunDebrief subscribers + 12d
--      operator dashboards: "show me every reconstruction Dataset that
--      cited refined CalibrationRevision X" via the GIN-friendly
--      `@>` operator (NOT `= ANY` — the 12b-3 gate-review finding:
--      `= ANY` is rewritten internally and does NOT probe a GIN index
--      on uuid[]).
--   2. Dataset-vs-Run consistency dashboards: comparing the two read
--      columns for the same producing_run_id surfaces "this Dataset
--      cited revision X but the Run never pinned it" — observable
--      drift, not a write-side block.
--
-- Additive forward-only migration:
--   - `used_calibrations uuid[] NOT NULL DEFAULT '{}'` so legacy pre-12c
--     rows backfill cleanly to an empty array (matches the in-memory
--     frozenset default + the `from_stored` forward-compat fold of
--     pre-12c `DatasetRegistered` payloads that lacked
--     `used_calibrations`).
--   - GIN index supports the `WHERE used_calibrations @> ARRAY[$N]::uuid[]`
--     filter pattern (mirrors Phase 12b-2's index on the symmetric
--     Run column).
--
-- Projection's `apply()` for `DatasetRegistered` is updated in the
-- same commit (`cora.data.projections.summary._INSERT_DATASET_SQL`)
-- to write `used_calibrations = payload.get("used_calibrations", [])`.

ALTER TABLE proj_data_dataset_summary
    ADD COLUMN used_calibrations UUID[] NOT NULL DEFAULT '{}';

CREATE INDEX proj_data_dataset_summary_used_calibrations_gin_idx
    ON proj_data_dataset_summary USING GIN (used_calibrations);
