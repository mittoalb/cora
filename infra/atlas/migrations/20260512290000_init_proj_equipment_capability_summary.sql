-- Phase 8e-3b: Equipment BC's second projection — capability summary.
--
-- Folds the Capability aggregate's lifecycle events into the
-- `proj_equipment_capability_summary` read model used by the
-- `list_capabilities` slice for `GET /capabilities` keyset-paginated
-- list endpoint with optional status filter.
--
-- Subscribed events:
--   - CapabilityDefined   -> INSERT (status=Defined, version_tag=NULL)
--   - CapabilityVersioned -> UPDATE status=Versioned, version_tag=payload
--   - CapabilityDeprecated -> UPDATE status=Deprecated (version_tag preserved)
--
-- `version_tag` is nullable because Defined capabilities have no
-- version label yet; CapabilityVersioned sets it; CapabilityDeprecated
-- leaves it alone (the audit trail preserves the historical label
-- of when the capability was last revised).
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_equipment_capability_summary (
    capability_id  UUID        PRIMARY KEY,
    name           TEXT        NOT NULL,
    status         TEXT        NOT NULL CHECK (
        status IN ('Defined', 'Versioned', 'Deprecated')
    ),
    version_tag    TEXT,
    created_at     TIMESTAMPTZ NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_equipment_capability_summary_keyset_idx
    ON proj_equipment_capability_summary (created_at, capability_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_equipment_capability_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_equipment_capability_summary')
ON CONFLICT DO NOTHING;
