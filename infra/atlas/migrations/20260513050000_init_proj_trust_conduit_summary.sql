-- Phase 8e-8: Trust BC's second projection, conduit summary.
--
-- Folds the Conduit aggregate's ConduitDefined event into the
-- `proj_trust_conduit_summary` read model used by the
-- `list_conduits` slice for `GET /conduits` keyset-paginated list
-- endpoint.
--
-- Subscribed events:
--   - ConduitDefined  -> INSERT (id + name + source_zone_id +
--                                target_zone_id + occurred_at)
--
-- ConduitLogbookOpened/Closed events are intentionally NOT
-- subscribed: they are internal logbook bookkeeping and don't
-- mutate conduit-summary state. Same precedent as Decision's
-- summary projection skipping its DecisionLogbookOpened/Closed.
-- A future `proj_trust_conduit_logbooks` join projection covers
-- "list conduits with N+ traversals in window" if that use case
-- crystallizes.
--
-- Filters: source_zone_id and target_zone_id (both NOT NULL on the
-- aggregate, so full indexes per the established convention; cf.
-- proj_run_summary_plan_idx which is full because plan_id is
-- NOT NULL).
--
-- Conduit is immutable-once-defined for Phase 8e-8 (lifecycle
-- additions deferred per the additive-state pattern; no `status`
-- column today).
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_trust_conduit_summary (
    conduit_id      UUID        PRIMARY KEY,
    name            TEXT        NOT NULL,
    source_zone_id  UUID        NOT NULL,
    target_zone_id  UUID        NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_trust_conduit_summary_keyset_idx
    ON proj_trust_conduit_summary (created_at, conduit_id);

CREATE INDEX proj_trust_conduit_summary_source_zone_idx
    ON proj_trust_conduit_summary (source_zone_id);

CREATE INDEX proj_trust_conduit_summary_target_zone_idx
    ON proj_trust_conduit_summary (target_zone_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_trust_conduit_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_trust_conduit_summary')
ON CONFLICT DO NOTHING;
