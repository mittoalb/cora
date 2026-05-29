-- Phase visit-delta: initialise the proj_trust_surface_active_visit
-- read model -- the "who drives this Surface right now?" projection.
--
-- Per [[project_visit_aggregate_design]] Phase delta:
--   - Surface aggregate state stays infrastructure-stable (no
--     active_visit_id column on the Surface state). The dynamic
--     concern lives entirely on this projection table.
--   - Schema: append-on-take + mark-on-release. PRIMARY KEY includes
--     since_at so replay-ordering of `Took(A) -> Released(A) -> Took(B)`
--     can never overwrite each other; closes P1-Impl-2 from Phase alpha
--     gate review.
--   - VisitTookControlOfSurface projection logic is a 2-statement
--     transaction:
--       1. UPDATE proj_trust_surface_active_visit
--          SET released_at = $occurred_at
--          WHERE surface_id = $1 AND released_at IS NULL
--                AND since_at < $occurred_at
--          (mark prior holder released at same instant. The since_at
--          predicate ensures a replayed-older Took cannot stomp a
--          newer open row.)
--       2. INSERT INTO proj_trust_surface_active_visit
--          (surface_id, visit_id, since_at, released_at)
--          VALUES ($1, $2, $3, NULL)
--          ON CONFLICT (surface_id, visit_id, since_at) DO NOTHING
--          (Partial UNIQUE on (surface_id) WHERE released_at IS NULL
--          enforces at-most-one-open-row across concurrent take
--          commands on sibling Visit streams.)
--   - VisitReleasedControlOfSurface projection logic:
--       UPDATE proj_trust_surface_active_visit
--       SET released_at = $occurred_at
--       WHERE surface_id = $1 AND visit_id = $2 AND released_at IS NULL
--       (naturally idempotent on replay)
--   - Active-controller query:
--       SELECT visit_id FROM proj_trust_surface_active_visit
--       WHERE surface_id = ? AND released_at IS NULL
--       ORDER BY since_at DESC LIMIT 1
--     LIMIT 1 + ORDER BY is defensive; invariant says at most one row
--     matches per surface (enforced by the take_control projection's
--     mark-prior-released step + decider's part_of descendant check).
--
-- FK to proj_trust_visit_summary(visit_id) so test cleanup cascades
-- naturally; production never deletes Visits (event log is append-only).

CREATE TABLE proj_trust_surface_active_visit (
    surface_id   UUID        NOT NULL,
    visit_id     UUID        NOT NULL,
    since_at     TIMESTAMPTZ NOT NULL,
    released_at  TIMESTAMPTZ,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (surface_id, visit_id, since_at),
    FOREIGN KEY (visit_id) REFERENCES proj_trust_visit_summary(visit_id) ON DELETE CASCADE
);

-- "Who is currently driving this Surface?" -- the dominant query.
-- Partial UNIQUE not just plain index: enforces the "at most one open
-- row per surface" invariant at the DB layer. Without it, two
-- concurrent take_control commands from sibling Visits on different
-- Visit streams could both pass the projection-snapshot check (the
-- per-stream optimistic-concurrency check protects nothing across
-- streams) and both insert open rows. With the partial unique, the
-- loser's 2-statement projection transaction raises UniqueViolation
-- on statement 2; the outer projection-batch transaction rolls back
-- (bookmark un-advanced); the projection worker backs off and retries.
-- By the time the retry runs, the winner's INSERT is committed and
-- visible, so the loser's statement 1 now sees the winner's row as
-- the prior holder and closes it, after which statement 2 INSERTs the
-- loser's row cleanly. Resolution comes from "competitor's INSERT is
-- now visible," not from any rollback semantics intrinsic to a nested
-- SAVEPOINT.
CREATE UNIQUE INDEX proj_trust_surface_active_visit_open_idx
    ON proj_trust_surface_active_visit (surface_id)
    WHERE released_at IS NULL;

-- "All Surfaces this Visit has held (history)" -- for per-Visit control history.
CREATE INDEX proj_trust_surface_active_visit_visit_idx
    ON proj_trust_surface_active_visit (visit_id, since_at);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_trust_surface_active_visit TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_trust_surface_active_visit')
ON CONFLICT DO NOTHING;
