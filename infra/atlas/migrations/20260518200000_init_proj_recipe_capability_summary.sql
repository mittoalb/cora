-- Phase 6k: Recipe BC's new Capability aggregate projection.
--
-- Folds the universal Capability aggregate's lifecycle events
-- (CapabilityDefined / CapabilityVersioned / CapabilityDeprecated)
-- into the `proj_recipe_capability_summary` read model that backs
-- `GET /capabilities/{capability_id}` and future list endpoints.
--
-- Distinct from `proj_equipment_family_summary` (renamed in 5i from
-- proj_equipment_capability_summary). Family is the Equipment BC's
-- device-class aggregate; Capability is the Recipe BC's operations-
-- layer template (DLM-B). The two aggregates are orthogonal axes
-- per [[project-capability-research]] Round 1+2.
--
-- Subscribed events:
--   - CapabilityDefined   -> INSERT (status=Defined, version_tag=NULL,
--                                    replaced_by_capability_id=NULL,
--                                    parameter_schema_present, etc.)
--   - CapabilityVersioned -> UPDATE status=Versioned + version_tag +
--                                    refresh required_affordances /
--                                    executor_shapes / description /
--                                    parameter_schema_present
--   - CapabilityDeprecated -> UPDATE status=Deprecated +
--                                    replaced_by_capability_id
--                                    (declarative fields PRESERVED for audit)
--
-- `version_tag` is nullable: Defined has no label until first version.
-- `replaced_by_capability_id` is nullable: Defined / Versioned never
-- have it; Deprecated may or may not (depending on whether the
-- operator pointed at a successor).
-- `parameter_schema_present` is a boolean (TRUE iff the latest event
-- carried a non-null parameter_schema); the schema content itself
-- lives in the event stream per [[project-pg-smart-logic-observation]]
-- to keep the summary table small.
-- `required_affordances` and `executor_shapes` ship as text[] for
-- future "list capabilities affording X" filter (deferred until
-- DLM-B / 6l Plan.activate validation needs it; columns present so
-- the next migration is an index add, not a column add).
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_recipe_capability_summary (
    capability_id              UUID        PRIMARY KEY,
    code                       TEXT        NOT NULL,
    name                       TEXT        NOT NULL,
    status                     TEXT        NOT NULL CHECK (
        status IN ('Defined', 'Versioned', 'Deprecated')
    ),
    version_tag                TEXT,
    description                TEXT,
    required_affordances       TEXT[]      NOT NULL DEFAULT ARRAY[]::TEXT[],
    executor_shapes            TEXT[]      NOT NULL DEFAULT ARRAY[]::TEXT[],
    parameter_schema_present   BOOLEAN     NOT NULL DEFAULT FALSE,
    replaced_by_capability_id  UUID,
    created_at                 TIMESTAMPTZ NOT NULL,
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_recipe_capability_summary_keyset_idx
    ON proj_recipe_capability_summary (created_at, capability_id);

CREATE UNIQUE INDEX proj_recipe_capability_summary_code_idx
    ON proj_recipe_capability_summary (code);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_recipe_capability_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_recipe_capability_summary')
ON CONFLICT DO NOTHING;
