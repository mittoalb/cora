-- Logbook-entry naming sweep (slice 4 of 4): rename Operation BC's
-- per-Procedure step entry table from "steps" to "activities" to match
-- the entry-class rename (`ProcedureStep` -> `Activity`).
--
-- Forward-only policy: NEW migration that compensates rather than
-- editing 20260515120000_init_entries_operation_procedure_steps.sql.
--
-- What changes:
--   - Table `entries_operation_procedure_steps` -> `entries_operation_procedure_activities`
--   - 4 indexes renamed to match (Postgres does NOT auto-rename indexes
--     when their table is renamed)
--
-- Greenfield-friendly: no production data exists yet, but the rename
-- is non-destructive (Postgres preserves all data through RENAME TABLE).
--
-- Companion concern: persisted `ProcedureStepsLogbookOpened` events whose
-- payload `kind` is the string "steps" are now misaligned with the
-- `LOGBOOK_KIND_ACTIVITY = "activities"` constant the evolver reads. The
-- event-class name itself is also renamed (ProcedureActivitiesLogbookOpened)
-- in the application layer. CORA is greenfield; no payload-rewrite
-- migration ships with this slice.
--
-- Altitude note: conductor's runtime `Step` union (SetpointStep |
-- ActionStep | CheckStep) is NOT renamed; the persisted entry/log is
-- now `Activity`. See operation/__init__.py module docstring "Step vs
-- Activity altitude split" for the deliberate vocabulary separation.

ALTER TABLE entries_operation_procedure_steps
    RENAME TO entries_operation_procedure_activities;

ALTER INDEX entries_operation_procedure_steps_proc_sampled_idx
    RENAME TO entries_operation_procedure_activities_proc_sampled_idx;

ALTER INDEX entries_operation_procedure_steps_proc_kind_sampled_idx
    RENAME TO entries_operation_procedure_activities_proc_kind_sampled_idx;

ALTER INDEX entries_operation_procedure_steps_logbook_idx
    RENAME TO entries_operation_procedure_activities_logbook_idx;

ALTER INDEX entries_operation_procedure_steps_recorded_at_brin_idx
    RENAME TO entries_operation_procedure_activities_recorded_at_brin_idx;
