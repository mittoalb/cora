-- Init proj_equipment_frame_children: parent -> child Frame join.
--
-- Subscribed events (see apps/api/src/cora/equipment/projections/
-- frame_children.py):
--   - FrameRegistered     -> INSERT when parent_frame_id IS NOT NULL
--                            (root frames skipped)
--   - FrameDecommissioned -> DELETE WHERE child_frame_id = $1
--
-- ## Shape
--
-- One row per (parent, child) edge in the Frame tree. The aggregate
-- state's `parent_frame_id` field is canonical; this projection
-- mirrors the edge set for tree walks (cycle defense at register
-- time, "list children of this node" queries).
--
-- ## Idempotency
--
-- INSERT uses ON CONFLICT DO NOTHING; DELETE is naturally idempotent.

CREATE TABLE proj_equipment_frame_children (
    parent_frame_id  UUID        NOT NULL,
    child_frame_id   UUID        NOT NULL,
    registered_at    TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (parent_frame_id, child_frame_id)
);

CREATE INDEX proj_equipment_frame_children_by_child_idx
    ON proj_equipment_frame_children (child_frame_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_equipment_frame_children TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_equipment_frame_children')
ON CONFLICT DO NOTHING;
