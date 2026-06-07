-- Phase 8e-7: Decision BC's first projection — decision summary.
--
-- Folds the Decision aggregate's DecisionRegistered event into the
-- `proj_decision_summary` read model used by the `list_decisions`
-- slice for `GET /decisions` keyset-paginated list endpoint.
--
-- Subscribed events:
--   - DecisionRegistered  -> INSERT (full genesis payload projected
--                                    + confidence_band derived from
--                                    confidence float at write time)
--
-- Decision is immutable per the BC's design (one event = one
-- decision; subsequent enrichments live on a separate reasoning-
-- entries stream). No status transitions; no UPDATE path.
--
-- DecisionLogbookOpened/Closed events are intentionally NOT
-- subscribed: they're internal logbook bookkeeping and don't
-- mutate decision-summary state.
--
-- ## Confidence band denormalization
--
-- The aggregate stores `confidence` as a float [0, 1]; the
-- ConfidenceBand (Low/Medium/High/Certain) is computed by
-- `confidence_band()` at read time. The projection precomputes the
-- band at INSERT for fast categorical filtering — same precedent
-- as Asset.lifecycle being stored as a string in
-- proj_equipment_asset_summary rather than re-derived from event
-- types on every read. The float is preserved as the source of
-- truth; the band is a denormalized view.
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_decision_summary (
    decision_id      UUID        PRIMARY KEY,
    decided_by       UUID        NOT NULL,
    decision_rule    TEXT,
    parent_id        UUID,
    confidence       DOUBLE PRECISION,
    confidence_band  TEXT        CHECK (
        confidence_band IS NULL
        OR confidence_band IN ('Low', 'Medium', 'High', 'Certain')
    ),
    created_at       TIMESTAMPTZ NOT NULL,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_decision_summary_keyset_idx
    ON proj_decision_summary (created_at, decision_id);

CREATE INDEX proj_decision_summary_decided_by_idx
    ON proj_decision_summary (decided_by);

CREATE INDEX proj_decision_summary_rule_idx
    ON proj_decision_summary (decision_rule)
    WHERE decision_rule IS NOT NULL;

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_decision_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_decision_summary')
ON CONFLICT DO NOTHING;
