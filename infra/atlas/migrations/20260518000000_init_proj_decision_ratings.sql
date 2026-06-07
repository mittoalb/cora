-- Phase 8f-b iter 1: operator acceptance-signal capture for Decisions.
--
-- The `DecisionRated` event (added to Decision aggregate) carries
-- (decision_id, rating, comment, rated_by, rated_at). The
-- evolver folds latest-per-actor wins into
-- `Decision.ratings: dict[UUID, DecisionRatingRecord]`. The
-- projection mirrors that latest-per-actor snapshot for efficient
-- query (typical pattern: "what's the latest rating from operator X
-- on Decision Y?" and "how many useful vs misleading ratings does
-- Decision Y have?").
--
-- Schema decisions:
--   - Composite PK (decision_id, rated_by): one row per
--     (decision, actor) pair. ON CONFLICT UPDATE implements the
--     latest-per-actor-wins fold at INSERT time.
--   - `rating TEXT NOT NULL CHECK IN (...)` matches the projection
--     code's `DecisionRating` StrEnum values.
--   - `comment TEXT NULL` (operator may omit).
--   - `rated_at TIMESTAMPTZ NOT NULL` is the canonical fold key
--     (latest wins).
--   - `confidence_at_rating DOUBLE PRECISION NULL` denormalizes
--     the rated Decision's confidence value at the time the rating
--     was recorded, so the (rating, confidence) pairs needed by a
--     future ConfidenceCalibrator (Platt scaling / isotonic
--     regression / LoRA uncertainty estimator) are queryable
--     without joining back to proj_decision_summary.
--   - Index on (decision_id) supports "all ratings on this Decision"
--     (PK partial). Index on (rated_by) supports "ratings
--     I have submitted across all Decisions" (audit / personal
--     dashboard).
--
-- Mutable read model; cora_app needs full DML. Bookmark row
-- inserted at sentinel (xid8 '0', position 0) so worker replays the
-- full event history on first advance.

CREATE TABLE proj_decision_ratings (
    decision_id              UUID        NOT NULL,
    rated_by        UUID        NOT NULL,
    rating                   TEXT        NOT NULL
                                         CHECK (rating IN ('useful', 'misleading', 'ignored')),
    comment                  TEXT,
    rated_at                 TIMESTAMPTZ NOT NULL,
    confidence_at_rating  DOUBLE PRECISION,
    PRIMARY KEY (decision_id, rated_by)
);

CREATE INDEX proj_decision_ratings_by_actor_idx
    ON proj_decision_ratings (rated_by);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_decision_ratings TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_decision_ratings')
ON CONFLICT DO NOTHING;
