-- Init proj_equipment_mount_lookup: slot_code -> mount_id.
--
-- Subscribed events (see apps/api/src/cora/equipment/projections/
-- mount_lookup.py):
--   - MountRegistered     -> INSERT (slot_code, mount_id, registered_at)
--                            with ON CONFLICT (slot_code) DO NOTHING
--   - MountDecommissioned -> DELETE WHERE mount_id = $1
--
-- Backs the register_mount slice's projection precondition:
-- slot codes must be unique across Active Mounts. A decommissioned
-- slot's code is freed (DELETE on decommission) so operators can
-- re-register the same code against a fresh stream.
--
-- UNIQUE(slot_code) is the load-bearing constraint; the
-- ON CONFLICT DO NOTHING in the projection handler is the
-- replay-safety guard for the same event seen twice.

CREATE TABLE proj_equipment_mount_lookup (
    slot_code      TEXT        PRIMARY KEY,
    mount_id       UUID        NOT NULL,
    registered_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX proj_equipment_mount_lookup_by_mount_idx
    ON proj_equipment_mount_lookup (mount_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_equipment_mount_lookup TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_equipment_mount_lookup')
ON CONFLICT DO NOTHING;
