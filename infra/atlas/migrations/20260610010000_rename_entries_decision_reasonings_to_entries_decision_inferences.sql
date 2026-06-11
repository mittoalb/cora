-- Logbook-entry naming sweep (slice 2 of 4): rename Decision's AI-trace
-- table from "reasonings" to "inferences" to match the entry-class rename
-- (`DecisionReasoning` -> `Inference`).
--
-- Forward-only policy: NEW migration that compensates rather than
-- editing 20260512200000_init_entries_decision_reasonings.sql.
--
-- What changes:
--   - Table `entries_decision_reasonings` -> `entries_decision_inferences`
--   - Indexes renamed to match (Postgres does NOT auto-rename indexes
--     when their table is renamed)
--
-- Greenfield-friendly: no production data exists yet, but the rename
-- is non-destructive (Postgres preserves all data through RENAME TABLE).
--
-- Companion concern: persisted `DecisionLogbookOpened` events whose
-- payload `kind` is the string "reasoning" are now misaligned with the
-- `LOGBOOK_KIND_INFERENCE = "inference"` constant the evolver reads. CORA
-- is greenfield, and unit/integration tests rebuild fresh streams per test.
-- No payload-rewrite migration ships with this slice.

ALTER TABLE entries_decision_reasonings
    RENAME TO entries_decision_inferences;

ALTER INDEX entries_decision_reasonings_decision_time_idx
    RENAME TO entries_decision_inferences_decision_time_idx;

ALTER INDEX entries_decision_reasonings_logbook_idx
    RENAME TO entries_decision_inferences_logbook_idx;

ALTER INDEX entries_decision_reasonings_conversation_idx
    RENAME TO entries_decision_inferences_conversation_idx;

ALTER INDEX entries_decision_reasonings_recorded_at_brin_idx
    RENAME TO entries_decision_inferences_recorded_at_brin_idx;
