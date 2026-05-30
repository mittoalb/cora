-- Init proj_equipment_asset_location: asset_id -> mount_id back-lookup.
--
-- The Asset aggregate does NOT carry installed_at: MountId per the
-- Mount/Frame Stage-1 design memo anti-hook. The back-lookup
-- ("where is this Asset right now?") lives in this projection.
--
-- Subscribed events (see apps/api/src/cora/equipment/projections/
-- asset_location.py):
--   - MountAssetInstalled   -> INSERT ON CONFLICT (asset_id) DO UPDATE
--                              (re-key on re-install at a different mount;
--                              same-mount re-install is a no-op)
--   - MountAssetUninstalled -> DELETE WHERE asset_id = $1
--
-- One row per Asset that is currently installed somewhere. The
-- previously_installed_asset_id field on MountAssetInstalled is
-- NOT consumed by this projection (the prior occupant's row was
-- already removed by the preceding MountAssetUninstalled event;
-- the design's no-implicit-eviction anti-hook ensures uninstall-
-- then-install ordering).

CREATE TABLE proj_equipment_asset_location (
    asset_id      UUID        PRIMARY KEY,
    mount_id      UUID        NOT NULL,
    installed_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX proj_equipment_asset_location_by_mount_idx
    ON proj_equipment_asset_location (mount_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_equipment_asset_location TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_equipment_asset_location')
ON CONFLICT DO NOTHING;
