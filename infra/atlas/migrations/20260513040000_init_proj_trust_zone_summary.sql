-- Phase 8e-8: Trust BC's first projection, zone summary.
--
-- Folds the Zone aggregate's ZoneDefined event into the
-- `proj_trust_zone_summary` read model used by the `list_zones`
-- slice for `GET /zones` keyset-paginated list endpoint.
--
-- Subscribed events:
--   - ZoneDefined  -> INSERT (id + name + occurred_at)
--
-- Zone is immutable-once-defined in Phase 8e-8 (the only event today
-- is ZoneDefined; lifecycle Defined -> Active -> Modified -> Archived
-- per BC-map is deferred per the additive-state pattern documented
-- in zone/state.py). Following the Decision precedent, the projection
-- ships without a `status` column today; a forward migration adds the
-- column with a CHECK constraint and a backfill default when the
-- first lifecycle slice ships.
--
-- No cross-aggregate refs to surface as filter columns: Zone is the
-- root of the Trust hierarchy. Filters are limited to cursor +
-- limit until lifecycle status arrives.
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_trust_zone_summary (
    zone_id     UUID        PRIMARY KEY,
    name        TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_trust_zone_summary_keyset_idx
    ON proj_trust_zone_summary (created_at, zone_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_trust_zone_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_trust_zone_summary')
ON CONFLICT DO NOTHING;
