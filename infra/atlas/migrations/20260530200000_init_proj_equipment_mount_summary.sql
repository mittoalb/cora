-- Init proj_equipment_mount_summary: read model for the Mount aggregate.
--
-- Subscribed events (see apps/api/src/cora/equipment/projections/
-- mount_summary.py):
--   - MountRegistered          -> INSERT (status=Active;
--                                 installed_asset_id=NULL; slot_code,
--                                 parent_mount_id, placement, drawing
--                                 from payload)
--   - MountDecommissioned      -> UPDATE status=Decommissioned
--   - MountPlacementUpdated    -> UPDATE placement
--   - MountAssetInstalled      -> UPDATE installed_asset_id = $asset_id
--   - MountAssetUninstalled    -> UPDATE installed_asset_id = NULL
--
-- Shape mirrors proj_equipment_frame_summary; placement + drawing as
-- jsonb (full 15-field Placement and 3-field Drawing payloads);
-- parent_mount_id and installed_asset_id nullable (top-level slots
-- and vacant slots respectively).
--
-- Indexes: primary key on mount_id; secondary on parent_mount_id for
-- tree walks; secondary on installed_asset_id (filtered to non-null)
-- supports the future "where is this Asset right now?" sweep
-- (denormalised mirror of proj_equipment_asset_location).

CREATE TABLE proj_equipment_mount_summary (
    mount_id            UUID        PRIMARY KEY,
    slot_code           TEXT        NOT NULL,
    parent_mount_id     UUID        NULL,
    placement           JSONB       NOT NULL,
    drawing             JSONB       NULL,
    installed_asset_id  UUID        NULL,
    status              TEXT        NOT NULL
                                    CHECK (status IN ('Active', 'Decommissioned')),
    created_at          TIMESTAMPTZ NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_equipment_mount_summary_parent_idx
    ON proj_equipment_mount_summary (parent_mount_id)
    WHERE parent_mount_id IS NOT NULL;

CREATE INDEX proj_equipment_mount_summary_installed_asset_idx
    ON proj_equipment_mount_summary (installed_asset_id)
    WHERE installed_asset_id IS NOT NULL;

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_equipment_mount_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_equipment_mount_summary')
ON CONFLICT DO NOTHING;
