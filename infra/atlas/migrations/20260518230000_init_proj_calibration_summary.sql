-- Phase 12a-2: Calibration BC's first projection — calibration summary read model.
--
-- Folds the Calibration aggregate's lifecycle events into the
-- `proj_calibration_summary` read model used by the `list_calibrations`
-- slice for `GET /calibrations` keyset-paginated list endpoint with
-- optional subsystem_or_asset_id / quantity / latest_revision_status /
-- latest_revision_source_kind filters.
--
-- Subscribed events:
--   - CalibrationDefined           -> INSERT (revision_count=0,
--                                             latest_revision_status=NULL,
--                                             latest_revision_source_kind=NULL,
--                                             last_revised_at=defined_at)
--   - CalibrationRevisionAppended  -> UPDATE revision_count += 1,
--                                            latest_revision_status,
--                                            latest_revision_source_kind,
--                                            last_revised_at
--
-- ## Identity uniqueness via Postgres jsonb (Q6 lock)
--
-- The UNIQUE constraint on `(subsystem_or_asset_id, quantity, operating_point)`
-- enforces the design memo's identity-tuple uniqueness invariant
-- WITHOUT RFC 8785 JCS canonicalisation. Postgres jsonb provides this
-- for free per the design memo Q6 lock:
--
--   - Key order is normalized on insert (`{a:1, b:2}` == `{b:2, a:1}`)
--   - Whitespace stripped
--   - Duplicate keys deduplicated (last-wins)
--   - Numeric values compared by value (`25 == 25.0`)
--
-- This is the entire reason RFC 8785 JCS was deliberately rejected in
-- the design memo's Round 3 — Kubernetes precedent: when you control
-- the schema, structural canonicalisation happens for free.
--
-- ## Latest-revision denormalisation
--
-- `latest_revision_status` + `latest_revision_source_kind` are
-- denormalised onto this summary table so the `list_calibrations`
-- filter doesn't need a JOIN against a per-revision table at query
-- time. They're updated on every `CalibrationRevisionAppended` apply.
-- For empty calibrations (no revisions yet) both columns are NULL.
--
-- The `source_kind` value is the lowercased class-name suffix of the
-- typed CalibrationSource union ("measured" / "computed" / "asserted")
-- computed at projection-write time from the exclusive-arc
-- `source_*_id` payload fields (Q5 lock).
--
-- ## Pagination + hot-path indexes
--
-- Keyset pagination on `(defined_at, calibration_id)`. `defined_at`
-- is set once at CalibrationDefined (immutable), so it's a stable
-- keyset key.
--
-- Scope partial index supports the hot-path "all calibrations for this
-- subsystem/asset" filter; quantity is appended to support the common
-- "rotation_center calibrations for this rotary stage" query.
--
-- A future per-revision projection (`proj_calibration_revisions`) can
-- land in 12a-3 if reconstruction pipelines need direct revision-level
-- queries; today the aggregate's event stream + `load_calibration`
-- handles single-aggregate revision reads.
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_calibration_summary (
    calibration_id              UUID        PRIMARY KEY,
    subsystem_or_asset_id       UUID        NOT NULL,
    quantity                    TEXT        NOT NULL,
    operating_point             JSONB       NOT NULL,
    description                 TEXT,
    defined_at                  TIMESTAMPTZ NOT NULL,
    last_revised_at             TIMESTAMPTZ NOT NULL,
    defined_by                  UUID        NOT NULL,
    revision_count              INTEGER     NOT NULL DEFAULT 0
        CHECK (revision_count >= 0),
    latest_revision_status      TEXT        CHECK (
        latest_revision_status IS NULL
        OR latest_revision_status IN ('Provisional', 'Verified')
    ),
    latest_revision_source_kind TEXT        CHECK (
        latest_revision_source_kind IS NULL
        OR latest_revision_source_kind IN ('measured', 'computed', 'asserted')
    ),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Identity-tuple uniqueness per Q6 lock: Postgres jsonb provides
    -- value-based equality (key-order normalization, numeric coercion
    -- 25 == 25.0, duplicate-key dedup) for free. No RFC 8785 JCS
    -- needed.
    CONSTRAINT proj_calibration_summary_identity_unique
        UNIQUE (subsystem_or_asset_id, quantity, operating_point)
);

-- Keyset pagination on `(defined_at, calibration_id)`.
CREATE INDEX proj_calibration_summary_keyset_idx
    ON proj_calibration_summary (defined_at, calibration_id);

-- Hot-path scope index: all calibrations OF this asset/subsystem,
-- optionally narrowed by quantity. Covers the common operator query
-- "what calibrations do we have for the Aerotech rotary?".
CREATE INDEX proj_calibration_summary_scope_idx
    ON proj_calibration_summary (subsystem_or_asset_id, quantity);

-- Filter index for "all Verified calibrations" (downstream consumers
-- want blessed values; this is the hot read path for reconstruction
-- consumers in 12c). Partial on the common case keeps the index small.
CREATE INDEX proj_calibration_summary_verified_idx
    ON proj_calibration_summary (subsystem_or_asset_id, quantity)
    WHERE latest_revision_status = 'Verified';

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_calibration_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_calibration_summary')
ON CONFLICT DO NOTHING;
