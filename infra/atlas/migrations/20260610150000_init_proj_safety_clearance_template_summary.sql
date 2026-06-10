-- Slice 9A: ClearanceTemplate aggregate projection — clearance template summary.
--
-- Folds the ClearanceTemplate aggregate's ClearanceTemplateDefined event into the
-- `proj_safety_clearance_template_summary` read model used by `list_clearance_templates`
-- (9A) and complements `get_clearance_template` (which uses fold-on-read).
--
-- Subscribed events (9A):
--   - ClearanceTemplateDefined -> INSERT (status='Draft', defined_at, defined_by)
--
-- Future slices (9B+9C) will subscribe to:
--   - ClearanceTemplateActivated  -> UPDATE status='Active'
--   - ClearanceTemplateDeprecated -> UPDATE status='Deprecated'
--   - ClearanceTemplateWithdrawn  -> UPDATE status='Withdrawn'
--
-- Status values are locked day one in the CHECK constraint so future
-- transitions land without a constraint migration.
--
-- ## Identity: stable opaque + facility-scoped typed address
--
-- `template_id` is the stable opaque handle (UUID PK). `(facility_code, code)`
-- is the operator-readable facility-scoped address; PARTIAL UNIQUE INDEX
-- enforces cross-stream uniqueness at projection-insert time (the aggregate
-- cannot enforce cross-stream invariants without DCB per project_deferred).
-- The PARTIAL index on `WHERE status != 'Withdrawn'` permits re-registering
-- a withdrawn template's address (similar to Supply decommission pattern).
--
-- ## Version tracking
--
-- `version` (default 1) + `supersedes_template_id` track version lineage.
-- The version-bump event and status transitions ship in 9B+9C; day-one
-- schema includes both fields so the table does not churn on 9B landing.
--
-- ## Audit columns
--
-- `defined_at` and `defined_by` denormalize the genesis event's timestamp
-- and actor for at-a-glance creation audit. Same precedent as
-- proj_equipment_family_summary.
--
-- ## Pagination index
--
-- Keyset pagination on `(defined_at, template_id)`. `defined_at` is set
-- once at ClearanceTemplateDefined (immutable), so it's a stable keyset key.
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_safety_clearance_template_summary (
    template_id               UUID        PRIMARY KEY,
    code                      TEXT        NOT NULL,
    title                     TEXT        NOT NULL,
    facility_code             TEXT        NOT NULL,
    version                   INTEGER     NOT NULL DEFAULT 1,
    supersedes_template_id    UUID,
    external_ref              TEXT,
    status                    TEXT        NOT NULL CHECK (
        status IN ('Draft', 'Active', 'Deprecated', 'Withdrawn')
    ),
    defined_at                TIMESTAMPTZ NOT NULL,
    defined_by                UUID        NOT NULL,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX proj_safety_clearance_template_summary_address_uq
    ON proj_safety_clearance_template_summary (facility_code, code)
    WHERE status != 'Withdrawn';

CREATE INDEX proj_safety_clearance_template_summary_keyset_idx
    ON proj_safety_clearance_template_summary (defined_at, template_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_safety_clearance_template_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_safety_clearance_template_summary')
ON CONFLICT DO NOTHING;
