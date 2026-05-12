-- Phase 8e-3a: Equipment BC's first projection — asset summary.
--
-- Folds the Asset aggregate's lifecycle + hierarchy events into a
-- queryable read model. Used by the `list_assets` slice for `GET
-- /assets` keyset-paginated list endpoint with optional level /
-- lifecycle / parent_id filters.
--
-- Subscribed events:
--   - AssetRegistered           -> INSERT (lifecycle=Commissioned)
--   - AssetActivated            -> UPDATE lifecycle=Active
--   - AssetDecommissioned       -> UPDATE lifecycle=Decommissioned
--   - AssetMaintenanceEntered   -> UPDATE lifecycle=Maintenance
--   - AssetRestoredFromMaintenance -> UPDATE lifecycle=Active
--   - AssetRelocated            -> UPDATE parent_id=to_parent_id
--
-- AssetCapabilityAdded / Removed are intentionally NOT subscribed
-- here; they describe the Asset<->Capability relationship, which
-- belongs in a future `proj_equipment_asset_capabilities` join
-- projection (deferred until a list-by-capability use case lands).
--
-- Hierarchy: the `parent_id` column is nullable because Enterprise-
-- level Assets have no parent. A future projection
-- (`proj_equipment_asset_subtree` or similar) could materialize the
-- transitive closure for "find all descendants of X" queries.
-- Today the flat parent_id is enough for direct-children lookups.
--
-- Mutable read model. cora_app gets full DML.
-- proj_equipment_asset_summary matches:
--   - the table name (here)
--   - the bookmark row (INSERT below)
--   - `AssetSummaryProjection.name` in
--     cora.equipment.projections.asset.

CREATE TABLE proj_equipment_asset_summary (
    asset_id    UUID        PRIMARY KEY,
    name        TEXT        NOT NULL,
    level       TEXT        NOT NULL CHECK (
        level IN ('Enterprise', 'Site', 'Area', 'Unit', 'Assembly', 'Device')
    ),
    lifecycle   TEXT        NOT NULL CHECK (
        lifecycle IN ('Commissioned', 'Active', 'Maintenance', 'Decommissioned')
    ),
    parent_id   UUID,
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_equipment_asset_summary_keyset_idx
    ON proj_equipment_asset_summary (created_at, asset_id);

-- Direct-children lookup support: `WHERE parent_id = $X` is the
-- "find all children of X" query. Partial index excludes NULL
-- (Enterprise root) since the lookup never targets nulls.
CREATE INDEX proj_equipment_asset_summary_parent_idx
    ON proj_equipment_asset_summary (parent_id)
    WHERE parent_id IS NOT NULL;

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_equipment_asset_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_equipment_asset_summary')
ON CONFLICT DO NOTHING;
