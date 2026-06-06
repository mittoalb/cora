-- Phase 11b-b: Caution BC's first projection -- caution summary read model.
--
-- Folds the Caution aggregate's lifecycle events into the
-- `proj_caution_summary` read model used by the `list_cautions` slice
-- for `GET /cautions` keyset-paginated list endpoint with optional
-- target_kind / target_id / category / severity / min_severity / status /
-- tag / author_actor_id filters.
--
-- Naming: the table contains rows for every lifecycle state (Active,
-- Superseded, Retired); the partial `..._target_active_idx` carries
-- the "Active hot-path" intent at the index layer.
--
-- Subscribed events:
--   - CautionRegistered  -> INSERT (status='Active', last_status_changed_at=NULL,
--                                   superseded_by_caution_id=NULL,
--                                   retired_reason=NULL,
--                                   parent_id=<None for top-level;
--                                              UUID for supersession child>)
--   - CautionSuperseded  -> UPDATE status='Superseded'
--                                  + superseded_by_caution_id (<child>)
--                                  + last_status_changed_at
--   - CautionRetired     -> UPDATE status='Retired'
--                                  + retired_reason (closed enum)
--                                  + last_status_changed_at
--
-- ## Identity: stable opaque + polymorphic target
--
-- `caution_id` is the stable opaque CORA UUID (PK). `target_kind` +
-- `target_id` denormalize the polymorphic `CautionTarget` VO (day-1
-- 2-arm union: Asset / Procedure) for at-a-glance display + the
-- target-active hot-path query (Run.start banner in 11b-c).
--
-- ## Audit columns
--
-- `last_status_changed_at` is nullable until the caution transitions
-- out of Active. `retired_reason` is set on Retired only; same
-- closed enum as `CautionRetireReason` (Resolved / NoLongerApplies /
-- WrongTarget). `superseded_by_caution_id` is set on the superseded
-- parent (links to its replacement). `parent_id` is set on
-- the supersession child genesis (links back to its parent).
--
-- The two pointers together form the supersession-lineage chain.
--
-- ## Pagination + hot-path indexes
--
-- Keyset pagination on `(registered_at, caution_id)`. `registered_at`
-- is set once at CautionRegistered (immutable), so it's a stable
-- keyset key.
--
-- Active-target partial index supports the future 11b-c Run.start
-- non-blocking banner lookup: "give me every Active caution attached
-- to this Asset / Procedure" needs an index seek, not a scan.
--
-- Tags GIN supports the `WHERE $N = ANY(tags)` filter pattern (mirrors
-- the safety BC's per-binding GIN indexes).
--
-- Author B-tree supports the "cautions I authored" filter (common in
-- EHS-style operator dashboards; keeping it day-1 trades cheap write
-- overhead for query convenience).
--
-- Status filtering uses the partial index (default filter is
-- `status='Active'`) -- no separate status btree.
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_caution_summary (
    caution_id                UUID        PRIMARY KEY,
    target_kind               TEXT        NOT NULL CHECK (
        target_kind IN ('Asset', 'Procedure')
    ),
    target_id                 UUID        NOT NULL,
    category                  TEXT        NOT NULL CHECK (
        category IN ('Wear', 'Calibration', 'Wiring',
                     'OperationalWindow', 'InterlockQuirk', 'ProcedureGotcha')
    ),
    severity                  TEXT        NOT NULL CHECK (
        severity IN ('Notice', 'Caution', 'Warning')
    ),
    text                      TEXT        NOT NULL,
    workaround                TEXT        NOT NULL,
    author_actor_id           UUID        NOT NULL,
    tags                      TEXT[]      NOT NULL DEFAULT '{}',
    expires_at                TIMESTAMPTZ,
    propagate_to_children     BOOLEAN     NOT NULL DEFAULT FALSE,
    status                    TEXT        NOT NULL CHECK (
        status IN ('Active', 'Superseded', 'Retired')
    ),
    parent_id                 UUID,
    superseded_by_caution_id  UUID,
    retired_reason            TEXT        CHECK (
        retired_reason IS NULL OR retired_reason IN (
            'Resolved', 'NoLongerApplies', 'WrongTarget'
        )
    ),
    registered_at             TIMESTAMPTZ NOT NULL,
    last_status_changed_at    TIMESTAMPTZ,
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Keyset pagination on `(registered_at, caution_id)`.
CREATE INDEX proj_caution_summary_keyset_idx
    ON proj_caution_summary (registered_at, caution_id);

-- Hot-path partial index for "all Active cautions on this target"
-- (Run.start banner lookup in 11b-c, plus list_cautions default scope).
-- Keeps the "_target_active" name as the partial-filter signal.
CREATE INDEX proj_caution_summary_target_active_idx
    ON proj_caution_summary (target_kind, target_id)
    WHERE status = 'Active';

-- GIN index for `$N = ANY(tags)` filter on list_cautions.
CREATE INDEX proj_caution_summary_tags_gin_idx
    ON proj_caution_summary USING GIN (tags);

-- "Cautions I authored" filter (operator dashboard).
CREATE INDEX proj_caution_summary_author_idx
    ON proj_caution_summary (author_actor_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_caution_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_caution_summary')
ON CONFLICT DO NOTHING;
