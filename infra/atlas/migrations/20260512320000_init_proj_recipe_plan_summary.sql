-- Phase 8e-4c: Recipe BC's third projection — plan summary.
--
-- Folds the Plan aggregate's lifecycle events into the
-- `proj_recipe_plan_summary` read model used by the `list_plans`
-- slice for `GET /plans` keyset-paginated list endpoint with
-- optional status + practice_id filters.
--
-- Subscribed events:
--   - PlanDefined    -> INSERT (status=Defined, version_tag=NULL,
--                               practice_id + method_id from payload)
--   - PlanVersioned  -> UPDATE status=Versioned, version_tag=payload
--   - PlanDeprecated -> UPDATE status=Deprecated (version_tag preserved)
--
-- Plan carries `practice_id` + `method_id` as cross-aggregate refs
-- in the genesis event. Both surface in the projection. The Plan's
-- `asset_ids` (the multi-asset binding) is intentionally NOT in this
-- projection: it's a list, the keyset+filter shape doesn't need it,
-- and a future `proj_recipe_plan_assets` join projection can carry
-- it when use cases demand "all plans using Asset X".
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_recipe_plan_summary (
    plan_id        UUID        PRIMARY KEY,
    name           TEXT        NOT NULL,
    practice_id    UUID        NOT NULL,
    method_id      UUID        NOT NULL,
    status         TEXT        NOT NULL CHECK (
        status IN ('Defined', 'Versioned', 'Deprecated')
    ),
    version_tag    TEXT,
    created_at     TIMESTAMPTZ NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_recipe_plan_summary_keyset_idx
    ON proj_recipe_plan_summary (created_at, plan_id);

CREATE INDEX proj_recipe_plan_summary_practice_idx
    ON proj_recipe_plan_summary (practice_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_recipe_plan_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_recipe_plan_summary')
ON CONFLICT DO NOTHING;
