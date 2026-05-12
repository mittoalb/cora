-- Phase 8e-4a: Recipe BC's first projection — method summary.
--
-- Folds the Method aggregate's lifecycle events into the
-- `proj_recipe_method_summary` read model used by the
-- `list_methods` slice for `GET /methods` keyset-paginated
-- list endpoint with optional status filter.
--
-- Subscribed events:
--   - MethodDefined    -> INSERT (status=Defined, version_tag=NULL)
--   - MethodVersioned  -> UPDATE status=Versioned, version_tag=payload
--   - MethodDeprecated -> UPDATE status=Deprecated (version_tag preserved)
--
-- Same shape as proj_equipment_capability_summary (the precedent
-- for the Defined/Versioned/Deprecated trio); `version_tag`
-- nullable for the same reason.
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_recipe_method_summary (
    method_id      UUID        PRIMARY KEY,
    name           TEXT        NOT NULL,
    status         TEXT        NOT NULL CHECK (
        status IN ('Defined', 'Versioned', 'Deprecated')
    ),
    version_tag    TEXT,
    created_at     TIMESTAMPTZ NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_recipe_method_summary_keyset_idx
    ON proj_recipe_method_summary (created_at, method_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_recipe_method_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_recipe_method_summary')
ON CONFLICT DO NOTHING;
