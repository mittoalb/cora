-- Phase 8e-1b: first projection table — actor summary for `GET /actors`.
--
-- Folds the Access BC's `ActorRegistered` + `ActorDeactivated` events
-- into a queryable read model. Used by the `list_actors` slice (8e-1c)
-- for the `GET /actors` keyset-paginated list endpoint.
--
-- Schema decisions:
--   - `actor_id` PK is the natural key — one row per actor, lifecycle
--     state collapsed to a single row by `ON CONFLICT` semantics in
--     the projection's `apply()`.
--   - `status` is the discriminator: 'active' (default after
--     ActorRegistered) -> 'deactivated' (after ActorDeactivated).
--     CHECK constraint catches typos in the projection code.
--   - `created_at` is the canonical Phase-8e D9 keyset-pagination key
--     paired with `actor_id`; every projection table follows this
--     convention so list endpoints share one cursor format. The index
--     on `(created_at, actor_id)` makes the keyset query
--     `WHERE (created_at, actor_id) > ($cursor)` an index-ordered scan.
--   - `updated_at` for operator visibility (when did this projection
--     last reflect a change for this actor?).
--
-- Mutable read model (rebuildable from events). cora_app needs full
-- DML; the arch-fitness test `test_projection_grants` enforces this
-- GRANT exists. Projection name `proj_access_actor_summary` matches:
--   - the table name (here)
--   - the bookmark row (INSERT below)
--   - `ActorSummaryProjection.name` (cora.access.projections.actor_summary)
-- The arch-fitness test `test_projection_table_match` enforces the
-- registration <-> table alignment.

CREATE TABLE proj_access_actor_summary (
    actor_id    UUID        PRIMARY KEY,
    name        TEXT        NOT NULL,
    status      TEXT        NOT NULL CHECK (status IN ('active', 'deactivated')),
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_access_actor_summary_keyset_idx
    ON proj_access_actor_summary (created_at, actor_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_access_actor_summary TO cora_app;

-- First-run sentinel: bookmark row inserted at the (xid8 '0',
-- position 0) sentinel so the worker replays the entire event
-- history into the projection on first advance. ON CONFLICT DO
-- NOTHING makes the migration idempotent.
INSERT INTO projection_bookmarks (name)
VALUES ('proj_access_actor_summary')
ON CONFLICT DO NOTHING;
