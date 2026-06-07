-- Phase 11a-b iter 2: Safety BC's first projection -- clearance summary.
--
-- Folds the Clearance aggregate's lifecycle events into the
-- `proj_safety_clearance_summary` read model used by the
-- `list_clearances` slice for `GET /clearances` keyset-paginated list
-- endpoint with optional kind / status / risk_band / facility_asset_id /
-- binds_to_subject_id / binds_to_asset_id / binds_to_run_id /
-- binds_to_procedure_id filters.
--
-- Subscribed events:
--   - ClearanceRegistered          -> INSERT (status='Defined', last_status_*=NULL,
--                                             last_reviewed_by=NULL)
--   - ClearanceSubmitted           -> UPDATE status='Submitted'   + status-change ts
--   - ClearanceUnderReview         -> UPDATE status='UnderReview' + status-change ts
--   - ClearanceReviewStepRecorded  -> (no projection update; reviewer chain lives
--                                       on the aggregate stream and is fetched via
--                                       get_clearance only; not surfaced in list view
--                                       to keep the projection narrow per cross-BC
--                                       precedent of NOT projecting per-substream rows)
--   - ClearanceApproved            -> UPDATE status='Approved'    + status-change ts
--                                                                 + last_reviewed_by
--                                                                 + valid_from / valid_until (if provided)
--   - ClearanceRejected            -> UPDATE status='Rejected'    + status-change ts
--                                                                 + last_status_reason
--                                                                 + last_reviewed_by
--   - ClearanceActivated           -> UPDATE status='Active'      + status-change ts
--
-- 11a-c will add (additive, no migration needed if columns nullable):
--   - ClearanceExpired             -> UPDATE status='Expired'     + status-change ts
--                                                                 + last_status_reason
--   - ClearanceSuperseded          -> UPDATE status='Superseded'  + status-change ts
--
-- ## Identity: stable opaque + denormalized display fields
--
-- `clearance_id` is the stable opaque CORA UUID (PK). `kind`, `title`,
-- `external_id`, `risk_band`, `facility_asset_id` are denormalized for
-- at-a-glance list display + filter querying.
--
-- ## Binding-id arrays + GIN indexes
--
-- 11a-a's multi-binding (`frozenset[ClearanceBinding]`) shape carries
-- 5 union arms: SubjectBinding / AssetBinding / RunBinding /
-- ProcedureBinding / ExternalBinding. The four CORA-aggregate-typed
-- arms are flattened into 4 UUID[] columns + GIN indexes for
-- `WHERE $1 = ANY(<binding>_ids)` filter pattern. ExternalBinding
-- (anti-corruption refs to upstream-deferred concepts like Proposal /
-- BTR / LabVisit) is NOT projected: those refs flow into the read
-- side via separate query if/when needed (no consumer demands it
-- today; same defer-until-consumer-needs precedent as ConduitTraversal
-- + RunReading projections).
--
-- ## Audit columns
--
-- `last_status_changed_at` is set on every transition. `last_status_reason`
-- is set on Rejected (will also be set on Expired in 11a-c). Approved /
-- Activated are happy-path; no reason column populated.
--
-- `last_reviewed_by` denormalized for at-a-glance "who approved /
-- rejected this" without requiring a join to the reviewers chain.
--
-- ## Pagination index
--
-- Keyset pagination on `(registered_at, clearance_id)`. Per-filter B-tree
-- indexes on `(status)`, `(kind)`, `(risk_band)`, `(facility_asset_id)`
-- are deferred per 8e precedent: revisit when a slow-query incident
-- surfaces.
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_safety_clearance_summary (
    clearance_id              UUID        PRIMARY KEY,
    kind                      TEXT        NOT NULL CHECK (
        kind IN ('ESAF', 'SAF', 'AForm', 'DUO', 'ESRA', 'ERA', 'PLHD',
                 'DOOR', 'BTR', 'Form9')
    ),
    facility_asset_id         UUID        NOT NULL,
    title                     TEXT        NOT NULL,
    external_id               TEXT,
    status                    TEXT        NOT NULL CHECK (
        status IN ('Defined', 'Submitted', 'UnderReview', 'Approved',
                   'Active', 'Expired', 'Rejected', 'Superseded')
    ),
    risk_band                 TEXT        CHECK (
        risk_band IS NULL OR risk_band IN ('Green', 'Yellow', 'Red')
    ),
    subject_binding_ids       UUID[]      NOT NULL DEFAULT '{}',
    asset_binding_ids         UUID[]      NOT NULL DEFAULT '{}',
    run_binding_ids           UUID[]      NOT NULL DEFAULT '{}',
    procedure_binding_ids     UUID[]      NOT NULL DEFAULT '{}',
    parent_id                 UUID,
    registered_at             TIMESTAMPTZ NOT NULL,
    last_status_changed_at    TIMESTAMPTZ,
    last_status_reason        TEXT,
    last_reviewed_by UUID,
    valid_from                TIMESTAMPTZ,
    valid_until               TIMESTAMPTZ,
    next_review_due_at        TIMESTAMPTZ,
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_safety_clearance_summary_keyset_idx
    ON proj_safety_clearance_summary (registered_at, clearance_id);

-- GIN indexes for `WHERE $1 = ANY(<binding>_ids)` filters on list_clearances.
CREATE INDEX proj_safety_clearance_summary_subject_bindings_gin_idx
    ON proj_safety_clearance_summary USING GIN (subject_binding_ids);
CREATE INDEX proj_safety_clearance_summary_asset_bindings_gin_idx
    ON proj_safety_clearance_summary USING GIN (asset_binding_ids);
CREATE INDEX proj_safety_clearance_summary_run_bindings_gin_idx
    ON proj_safety_clearance_summary USING GIN (run_binding_ids);
CREATE INDEX proj_safety_clearance_summary_procedure_bindings_gin_idx
    ON proj_safety_clearance_summary USING GIN (procedure_binding_ids);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_safety_clearance_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_safety_clearance_summary')
ON CONFLICT DO NOTHING;
