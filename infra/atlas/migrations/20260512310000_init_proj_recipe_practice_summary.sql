-- Phase 8e-4b: Recipe BC's second projection — practice summary.
--
-- Folds the Practice aggregate's lifecycle events into the
-- `proj_recipe_practice_summary` read model used by the
-- `list_practices` slice for `GET /practices` keyset-paginated
-- list endpoint with optional status + method_id filters.
--
-- Subscribed events:
--   - PracticeDefined    -> INSERT (status=Defined, version_tag=NULL,
--                                   method_id + site_id from payload)
--   - PracticeVersioned  -> UPDATE status=Versioned, version_tag=payload
--   - PracticeDeprecated -> UPDATE status=Deprecated (version_tag preserved)
--
-- Practice carries `method_id` (which Method this Practice
-- implements) + `site_id` (which Site adopted it) as cross-aggregate
-- refs in the genesis event payload. Both surface in the projection
-- so list queries can filter "show me all Practices implementing
-- Method X" without rebinding the events. Once written they don't
-- change (the lifecycle events don't carry them again), so no
-- update path is needed.
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_recipe_practice_summary (
    practice_id    UUID        PRIMARY KEY,
    name           TEXT        NOT NULL,
    method_id      UUID        NOT NULL,
    site_id        UUID        NOT NULL,
    status         TEXT        NOT NULL CHECK (
        status IN ('Defined', 'Versioned', 'Deprecated')
    ),
    version_tag    TEXT,
    created_at     TIMESTAMPTZ NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_recipe_practice_summary_keyset_idx
    ON proj_recipe_practice_summary (created_at, practice_id);

CREATE INDEX proj_recipe_practice_summary_method_idx
    ON proj_recipe_practice_summary (method_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_recipe_practice_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_recipe_practice_summary')
ON CONFLICT DO NOTHING;
