-- Init proj_equipment_mount_children: parent -> child Mount join.
--
-- Subscribed events (see apps/api/src/cora/equipment/projections/
-- mount_children.py):
--   - MountRegistered     -> INSERT when parent_mount_id IS NOT NULL
--                            (top-level mounts skipped)
--   - MountDecommissioned -> DELETE WHERE child_mount_id = $1
--
-- Backs the decommission_mount slice's projection precondition:
-- a parent cannot be decommissioned while active children exist (no
-- cascade per the design anti-hook).
--
-- Mirrors proj_equipment_frame_children's shape.

CREATE TABLE proj_equipment_mount_children (
    parent_mount_id  UUID        NOT NULL,
    child_mount_id   UUID        NOT NULL,
    registered_at    TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (parent_mount_id, child_mount_id)
);

CREATE INDEX proj_equipment_mount_children_by_child_idx
    ON proj_equipment_mount_children (child_mount_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_equipment_mount_children TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_equipment_mount_children')
ON CONFLICT DO NOTHING;
