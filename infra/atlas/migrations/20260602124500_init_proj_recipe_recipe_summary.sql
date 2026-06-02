-- Recipe BC's new Recipe aggregate projection.
--
-- Folds the Recipe aggregate's lifecycle events
-- (RecipeDefined / RecipeVersioned / RecipeDeprecated) into the
-- `proj_recipe_recipe_summary` read model that backs
-- `GET /recipes/{recipe_id}` and future list endpoints.
--
-- Distinct from `proj_recipe_capability_summary`. Capability is the
-- declarative contract aggregate; Recipe is the deployment-bound
-- executable step body that references a Capability per
-- [[project-recipe-aggregate-design]]. The split was locked via
-- [[capability-naming-split-lock]] (Shape 2: 5-peer aggregates in
-- Recipe BC).
--
-- Subscribed events:
--   - RecipeDefined    -> INSERT (status=Defined, version_tag=NULL,
--                                 replaced_by_recipe_id=NULL,
--                                 steps_count from payload)
--   - RecipeVersioned  -> UPDATE status=Versioned + version_tag +
--                                 refresh steps_count
--                                 (a new version IS a new declaration)
--   - RecipeDeprecated -> UPDATE status=Deprecated +
--                                 replaced_by_recipe_id
--                                 (steps + capability_id PRESERVED
--                                  for audit)
--
-- `version_tag` is nullable: Defined has no label until first
-- version. `replaced_by_recipe_id` is nullable: Defined / Versioned
-- never have it; Deprecated may or may not (depending on whether
-- the operator pointed at a successor).
-- `steps_count` is the number of `RecipeStep`s in the latest event
-- (denormalized from the wire-format `{steps: {steps: [...]}}`
-- payload); the steps themselves live in the event stream per
-- [[project-pg-smart-logic-observation]] to keep the summary table
-- small.
--
-- Lifecycle timestamps (`versioned_at`, `deprecated_at`) ship as
-- nullable columns now; the projection updates them on the matching
-- event. Mirrors the May-2026 template-aggregate-timestamps sweep
-- across Family/Capability/Method/Plan/Practice.
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_recipe_recipe_summary (
    recipe_id              UUID        PRIMARY KEY,
    name                   TEXT        NOT NULL,
    capability_id          UUID        NOT NULL,
    status                 TEXT        NOT NULL CHECK (
        status IN ('Defined', 'Versioned', 'Deprecated')
    ),
    version_tag            TEXT,
    steps_count            INTEGER     NOT NULL DEFAULT 0,
    replaced_by_recipe_id  UUID,
    created_at             TIMESTAMPTZ NOT NULL,
    versioned_at           TIMESTAMPTZ,
    deprecated_at          TIMESTAMPTZ,
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_recipe_recipe_summary_keyset_idx
    ON proj_recipe_recipe_summary (created_at, recipe_id);

CREATE INDEX proj_recipe_recipe_summary_capability_id_idx
    ON proj_recipe_recipe_summary (capability_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_recipe_recipe_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_recipe_recipe_summary')
ON CONFLICT DO NOTHING;
