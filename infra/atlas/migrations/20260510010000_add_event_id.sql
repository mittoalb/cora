-- Add event_id column to events table.
--
-- `event_id` is the producer-assigned per-event identity (UUIDv7 in
-- production via the IdGenerator port). It serves three roles:
--   1. Dedup key for downstream consumers under at-least-once delivery
--      (projections, sagas) — the canonical event-sourcing pattern.
--   2. Natural value to use as the next command's `causation_id` in
--      saga / process-manager chains (Phase 3+).
--   3. Stable cross-database / cross-system reference for an event
--      (the `position` bigserial is local to one database and resets
--      on a fresh deploy; event_id is portable).
--
-- UNIQUE constraint enforces that producers never emit the same id
-- twice. The application generates one fresh UUIDv7 per emitted
-- event so collisions are astronomically unlikely; the constraint
-- catches the rare bug class where a wrapper accidentally reuses
-- an id (e.g. from a cached generator) before it surfaces as silent
-- duplicate-record corruption downstream.
--
-- Backfill strategy: greenfield, no production data exists yet, but
-- we still issue the standard ADD-NULLABLE / BACKFILL / SET-NOT-NULL
-- sequence so this migration is correct for any non-empty test or
-- staging database picked up before deploy.

ALTER TABLE events ADD COLUMN event_id uuid;

UPDATE events SET event_id = gen_random_uuid() WHERE event_id IS NULL;

ALTER TABLE events ALTER COLUMN event_id SET NOT NULL;

CREATE UNIQUE INDEX events_event_id_unique ON events (event_id);
