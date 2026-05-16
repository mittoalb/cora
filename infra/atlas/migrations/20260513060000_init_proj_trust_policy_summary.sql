-- Phase 8e-8: Trust BC's third projection, policy summary.
--
-- Folds the Policy aggregate's PolicyDefined event into the
-- `proj_trust_policy_summary` read model used by the
-- `list_policies` slice for `GET /policies` keyset-paginated list
-- endpoint.
--
-- Subscribed events:
--   - PolicyDefined  -> INSERT (id + name + conduit_id +
--                               occurred_at)
--
-- Filters: conduit_id (NOT NULL on the aggregate -> full index).
--
-- The list-typed `principals_permitted` and `commands_permitted`
-- payload fields are intentionally NOT projected as filter columns:
-- they are list-shaped and a future `proj_trust_policy_principals`
-- join projection covers "all policies allowing Principal X" if
-- that use case crystallizes (analog to the deferred
-- `proj_recipe_method_capabilities` join).
--
-- Policy is immutable-once-defined for Phase 8e-8 (lifecycle
-- Drafted -> Approved -> Active -> Superseded per BC-map deferred
-- per the additive-state pattern; no `status` column today).
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_trust_policy_summary (
    policy_id   UUID        PRIMARY KEY,
    name        TEXT        NOT NULL,
    conduit_id  UUID        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_trust_policy_summary_keyset_idx
    ON proj_trust_policy_summary (created_at, policy_id);

CREATE INDEX proj_trust_policy_summary_conduit_idx
    ON proj_trust_policy_summary (conduit_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_trust_policy_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_trust_policy_summary')
ON CONFLICT DO NOTHING;
