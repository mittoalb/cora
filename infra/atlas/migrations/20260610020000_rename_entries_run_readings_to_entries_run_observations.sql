-- Logbook-entry naming sweep (slice 3 of 4): rename Run's sensor/motor
-- entry table from "readings" to "observations" to match the entry-class
-- rename (`RunReading` -> `Observation`).
--
-- Forward-only policy: NEW migration that compensates rather than
-- editing 20260514040000_init_entries_run_readings.sql.
--
-- What changes:
--   - Table `entries_run_readings` -> `entries_run_observations`
--   - 4 indexes renamed to match (Postgres does NOT auto-rename indexes
--     when their table is renamed)
--
-- Greenfield-friendly: no production data exists yet, but the rename
-- is non-destructive (Postgres preserves all data through RENAME TABLE).
--
-- Companion concern: persisted `RunReadingLogbookOpened` events whose
-- payload `kind` is the string "reading" are now misaligned with the
-- `LOGBOOK_KIND_OBSERVATION = "observation"` constant the evolver reads.
-- The event-class name itself is also renamed (RunObservationLogbookOpened)
-- in the application layer. CORA is greenfield; no payload-rewrite
-- migration ships with this slice.

ALTER TABLE entries_run_readings
    RENAME TO entries_run_observations;

ALTER INDEX entries_run_readings_run_sampled_idx
    RENAME TO entries_run_observations_run_sampled_idx;

ALTER INDEX entries_run_readings_run_procedure_sampled_idx
    RENAME TO entries_run_observations_run_procedure_sampled_idx;

ALTER INDEX entries_run_readings_logbook_idx
    RENAME TO entries_run_observations_logbook_idx;

ALTER INDEX entries_run_readings_recorded_at_brin_idx
    RENAME TO entries_run_observations_recorded_at_brin_idx;
