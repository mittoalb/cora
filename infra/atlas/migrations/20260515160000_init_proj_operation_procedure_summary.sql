-- Phase 10c-c iter 2: Operation BC's first projection -- procedure summary.
--
-- Folds the Procedure aggregate's lifecycle events into the
-- `proj_operation_procedure_summary` read model used by the
-- `list_procedures` slice for `GET /procedures` keyset-paginated list
-- endpoint with optional status / kind / parent_run_id / target_asset_id
-- filters.
--
-- Subscribed events:
--   - ProcedureRegistered          -> INSERT (status='Defined', last_status_*=NULL,
--                                             interrupted_at=NULL, steps_logbook_id=NULL)
--   - ProcedureStarted             -> UPDATE status='Running' + last_status_changed_at
--   - ProcedureCompleted           -> UPDATE status='Completed' + last_status_changed_at
--   - ProcedureAborted             -> UPDATE status='Aborted' + last_status_changed_at
--                                                              + last_status_reason
--   - ProcedureTruncated           -> UPDATE status='Truncated' + last_status_changed_at
--                                                                + last_status_reason
--                                                                + interrupted_at
--   - ProcedureStepsLogbookOpened  -> UPDATE steps_logbook_id (status NOT touched;
--                                                              orthogonal to lifecycle)
--
-- ## Identity: stable opaque + denormalized display fields
--
-- `procedure_id` is the stable opaque handle (UUID PK). `name` and
-- `kind` are denormalized for at-a-glance list display; the canonical
-- shape lives in the aggregate event stream.
--
-- ## target_asset_ids: UUID[] with GIN index for ANY() filtering
--
-- `target_asset_ids` carried as a Postgres UUID[] column with GIN index
-- to support the `WHERE $1 = ANY(target_asset_ids)` filter pattern from
-- the list_procedures handler. Per-aggregate cardinality is small
-- (typical 1-5 target assets per procedure), so GIN scan cost is bounded.
-- Alternative join-table shape (proj_operation_procedure_target_assets)
-- was rejected: more migration surface, two-write projection apply for
-- ProcedureRegistered, no analytical query yet justifies the split.
--
-- ## Audit columns
--
-- `last_status_changed_at` is set on every transition (Started /
-- Completed / Aborted / Truncated). `last_status_reason` is set only
-- on Aborted + Truncated (Completed is happy-path, no reason). Same
-- denormalize-for-at-a-glance pattern as proj_supply_summary.
--
-- `interrupted_at` is Truncated-only: the operator's best guess at
-- when the actual interruption happened (distinct from
-- `last_status_changed_at`, which is when the truncate command was
-- processed).
--
-- `steps_logbook_id` is set by ProcedureStepsLogbookOpened (lazy on
-- first step append). NULL until the first step lands.
--
-- ## Pagination index
--
-- Keyset pagination on `(registered_at, procedure_id)`. `registered_at`
-- is set once at ProcedureRegistered (immutable), so it's a stable
-- keyset key. Cursor in the API encodes `(registered_at, procedure_id)`.
-- Per-filter B-tree indexes on `(status)` / `(kind)` / `(parent_run_id)`
-- are deferred per 8e precedent: revisit when a slow-query incident
-- surfaces.
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_operation_procedure_summary (
    procedure_id           UUID        PRIMARY KEY,
    name                   TEXT        NOT NULL,
    kind                   TEXT        NOT NULL,
    target_asset_ids       UUID[]      NOT NULL DEFAULT '{}',
    parent_run_id          UUID,
    status                 TEXT        NOT NULL CHECK (
        status IN ('Defined', 'Running', 'Completed', 'Aborted', 'Truncated')
    ),
    steps_logbook_id       UUID,
    registered_at          TIMESTAMPTZ NOT NULL,
    last_status_changed_at TIMESTAMPTZ,
    last_status_reason     TEXT,
    interrupted_at         TIMESTAMPTZ,
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_operation_procedure_summary_keyset_idx
    ON proj_operation_procedure_summary (registered_at, procedure_id);

-- GIN index for `WHERE $1 = ANY(target_asset_ids)` filter on list_procedures.
CREATE INDEX proj_operation_procedure_summary_target_assets_gin_idx
    ON proj_operation_procedure_summary USING GIN (target_asset_ids);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_operation_procedure_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_operation_procedure_summary')
ON CONFLICT DO NOTHING;
