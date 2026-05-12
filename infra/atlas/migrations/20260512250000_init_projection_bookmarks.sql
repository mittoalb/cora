-- Phase 8e-1a: projection bookmark table.
--
-- One row per registered projection (and per future saga / external
-- adapter, when they ship). The worker reads the bookmark to know
-- where to resume the advance scan, and updates it after each
-- successfully-processed batch in the same transaction as the
-- projection writes (atomic at-least-once delivery).
--
-- Schema rationale per the Phase-8e gate review (D4 + sanity-check
-- against Khyst + Dudycz):
--
--   - `name` is the primary key (one bookmark per subscriber).
--     Matches `Projection.name` in code; also serves as the
--     `proj_<bc>_<name>` table-name suffix by convention.
--   - `last_transaction_id xid8` is the canonical lexicographic-
--     cursor key. Default `'0'::xid8` is the sentinel that compares
--     less than any real transaction; new subscriptions registering
--     for the first time replay the entire event history on first
--     poll.
--   - `last_position bigint` is the secondary key for events within
--     the same transaction (one xid8 may cover N events with distinct
--     positions). Default 0 matches the sentinel.
--   - `updated_at` is for operator visibility (lag inspection: head
--     position - last_position; freshness: now() - updated_at).
--
-- This is a MUTABLE cache (rebuildable from events), not append-only,
-- so cora_app gets full DML — same pattern as `idempotency_keys`. The
-- arch-fitness test for append-only REVOKE explicitly excludes
-- bookmarks (the test scans `events` + `entries_*` only).
--
-- Per-projection bookmark rows are inserted by each projection's own
-- migration (`INSERT INTO projection_bookmarks (name) VALUES
-- ('proj_<bc>_<name>') ON CONFLICT DO NOTHING`) so the row exists
-- from the moment the projection is registered.

CREATE TABLE projection_bookmarks (
    name                TEXT        PRIMARY KEY,
    last_transaction_id xid8        NOT NULL DEFAULT '0'::xid8,
    last_position       BIGINT      NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON projection_bookmarks TO cora_app;
