-- Add `transaction_id xid8` column + composite advance index to events.
--
-- Phase-8e prep (lands before the projection-worker framework). Phase 1
-- already documented the projection sequence-rollback hazard in the
-- EventStore port docstring: a `bigserial position`-only cursor can skip
-- events from a slow transaction that committed AFTER a fast one with a
-- higher position. The canonical 2025-2026 fix (Khyst's
-- postgresql-event-sourcing reference + Dudycz's "Ordering in Postgres
-- Outbox") is to record `pg_current_xact_id()` (xid8, 64-bit
-- FullTransactionId, monotonic, no wraparound) on each event row and
-- have projection consumers advance via the lexicographic
-- `(transaction_id, position) > (last_tx, last_pos)` cursor with
-- `transaction_id < pg_snapshot_xmin(pg_current_snapshot())` exclusion
-- to skip in-flight transactions.
--
-- The `events_advance_idx` index supports the projection advance query
-- as an index-ordered scan; without it, Postgres sorts the table on
-- every batch (cheap at low volume, expensive once the events table
-- grows). Cheap to add now in greenfield; backfilling later means a
-- CONCURRENTLY index build under load.
--
-- DEFAULT pg_current_xact_id() means the application never writes this
-- column; it's always set by the database at INSERT time. Greenfield
-- (no production data), so backfill collapses to the DEFAULT clause.
--
-- Why xid8 not xid: xid is 32-bit and wraps every ~2 billion
-- transactions (PG handles this with vacuum freezing but apps must
-- not assume monotonicity). xid8 is 64-bit, monotonic, and cannot be
-- reused in the lifetime of a database cluster.
--
-- Why the column lives on `events` (not on `entries_*`): the projection
-- framework reads from `events` only. Entry tables are write-side
-- audit storage with their own per-category access patterns; if a
-- future entry-projection framework arrives, the same xid8 + advance-
-- index pattern can be added per-entry-table at that time.

ALTER TABLE events
    ADD COLUMN transaction_id xid8 NOT NULL DEFAULT pg_current_xact_id();

CREATE INDEX events_advance_idx ON events (transaction_id, position);
