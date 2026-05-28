-- Phase visit-gamma: initialise the proj_trust_visit_presence read model
-- backing per-Visit presence lookup.
--
-- Per [[project_visit_aggregate_design]] Phase gamma:
--   - Flatten Visit.presence_entries (frozenset[PresenceEntry] on
--     aggregate state) into per-row records in a separate child table.
--     The aggregate carries the collection for decider invariants;
--     the projection denormalizes for efficient query.
--   - Composite PK (visit_id, actor_id, check_in_at) matches the
--     decider invariant: at most one PresenceEntry per (actor, check_in_at)
--     per Visit. Multi-shift (same actor checking in / out repeatedly)
--     is supported because each cycle gets a distinct check_in_at.
--   - FK to proj_trust_visit_summary(visit_id) with ON DELETE CASCADE:
--     if a Visit is ever projection-deleted (e.g., test cleanup),
--     presence rows cascade. Production never deletes Visits (event
--     log is append-only).
--   - mode CHECK constraint enforces the closed PresenceMode enum
--     {physical, remote}; adding a new value uses CORA's forward-only
--     migration pattern (drop + re-add per [[project_forward_only_migrations]]).
--
-- Subscribed events:
--   - VisitCheckedIn  -> INSERT (actor_id, mode, check_in_at, check_out_at=NULL)
--                       ON CONFLICT DO NOTHING (replay idempotency)
--   - VisitCheckedOut -> UPDATE SET check_out_at = occurred_at
--                       WHERE visit_id=... AND actor_id=...
--                       AND check_out_at IS NULL
--                       (naturally idempotent: replay finds no open row,
--                       UPDATE matches zero rows, no-op)

CREATE TABLE proj_trust_visit_presence (
    visit_id     UUID        NOT NULL,
    actor_id     UUID        NOT NULL,
    mode         TEXT        NOT NULL CHECK (mode IN ('physical', 'remote')),
    check_in_at  TIMESTAMPTZ NOT NULL,
    check_out_at TIMESTAMPTZ,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (visit_id, actor_id, check_in_at),
    FOREIGN KEY (visit_id) REFERENCES proj_trust_visit_summary(visit_id) ON DELETE CASCADE
);

-- "Who is currently checked in to this Visit?"
CREATE INDEX proj_trust_visit_presence_visit_open_idx
    ON proj_trust_visit_presence (visit_id)
    WHERE check_out_at IS NULL;

-- "Where has this actor been present?" -- for per-actor presence history.
CREATE INDEX proj_trust_visit_presence_actor_idx
    ON proj_trust_visit_presence (actor_id, check_in_at);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_trust_visit_presence TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_trust_visit_presence')
ON CONFLICT DO NOTHING;
