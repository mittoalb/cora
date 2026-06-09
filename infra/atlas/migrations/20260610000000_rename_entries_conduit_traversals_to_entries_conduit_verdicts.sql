-- Logbook-entry naming sweep (slice 1 of 4): rename Conduit's audit-log
-- table from "traversals" to "verdicts" to match the entry-class rename
-- (`ConduitTraversal` -> `Verdict`).
--
-- The naming sweep landed in code as a single slice; this migration
-- brings the schema in line. Forward-only policy
-- (project_forward_only_migrations.md): we add a NEW migration that
-- compensates rather than editing 20260512000000.
--
-- What changes:
--   - Table `entries_conduit_traversals` -> `entries_conduit_verdicts`
--   - Three indexes renamed to match (Postgres does NOT auto-rename
--     indexes when their table is renamed)
--
-- Greenfield-friendly: no production data exists yet, but the rename
-- is non-destructive (Postgres preserves all data through RENAME TABLE).
-- Safe to apply against any non-empty test or staging database picked
-- up before deploy.
--
-- Companion concern: persisted `ConduitLogbookOpened` events whose
-- payload `kind` is the string "traversals" are now misaligned with the
-- `LOGBOOK_KIND_VERDICT = "verdicts"` constant the evolver reads. CORA
-- is greenfield (no production event stores in scope), and unit/integration
-- tests rebuild fresh streams per test. No payload-rewrite migration ships
-- with this slice. If a deployment surfaces stored "traversals"-kind
-- events, the rewrite is a separate forward-only migration.

ALTER TABLE entries_conduit_traversals
    RENAME TO entries_conduit_verdicts;

ALTER INDEX entries_conduit_traversals_conduit_time_idx
    RENAME TO entries_conduit_verdicts_conduit_time_idx;

ALTER INDEX entries_conduit_traversals_logbook_idx
    RENAME TO entries_conduit_verdicts_logbook_idx;

ALTER INDEX entries_conduit_traversals_recorded_at_brin_idx
    RENAME TO entries_conduit_verdicts_recorded_at_brin_idx;
