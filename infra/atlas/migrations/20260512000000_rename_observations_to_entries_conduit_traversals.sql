-- Phase 6f-5a post-cleanup: rename "observation" + "channel" naming
-- to "entry" + "logbook" naming.
--
-- The naming sweep landed in code as a single follow-up commit; this
-- migration brings the schema in line. Forward-only policy
-- (project_forward_only_migrations.md): we add a NEW migration that
-- compensates rather than editing the original 20260511130000_init
-- migration.
--
-- What changes:
--   - Table `observations_conduit_traversals` → `entries_conduit_traversals`
--   - Column `channel_id` → `logbook_id` (still UUID NOT NULL)
--   - Three indexes get renamed to match (Postgres does NOT auto-rename
--     indexes when their table is renamed)
--
-- Greenfield-friendly: no production data exists yet, but the rename
-- is non-destructive (Postgres preserves all data through RENAME TABLE
-- / RENAME COLUMN). Safe to apply against any non-empty test or
-- staging database picked up before deploy.
--
-- Why these renames now: the 6f-5a audit-review cleanup landed on
-- "Logbook + Entry" as the cleanest naming pair after evaluating
-- Channel + Observation (EPICS overlap), Series + Observation
-- (technical), Log + Entry (logging-module proximity), Register +
-- Entry (verb-collision with our register_* slices), Channel + Record
-- (DB-record overlap on entry side). Logbook + Entry has zero
-- collisions, idiomatic English pairing ("logbook entry"), audit-grade
-- regulatory fit (21 CFR Part 11 / ISO 17025). Locked.

ALTER TABLE observations_conduit_traversals
    RENAME TO entries_conduit_traversals;

ALTER TABLE entries_conduit_traversals
    RENAME COLUMN channel_id TO logbook_id;

ALTER INDEX observations_conduit_traversals_conduit_time_idx
    RENAME TO entries_conduit_traversals_conduit_time_idx;

ALTER INDEX observations_conduit_traversals_channel_idx
    RENAME TO entries_conduit_traversals_logbook_idx;

ALTER INDEX observations_conduit_traversals_recorded_at_brin_idx
    RENAME TO entries_conduit_traversals_recorded_at_brin_idx;
