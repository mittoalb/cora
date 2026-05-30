-- Init proj_equipment_frame_consumers: references TO a Frame.
--
-- A "consumer" is any aggregate that holds a reference to a Frame
-- in a way that would break if the Frame were decommissioned. In
-- Phase B that means child Frames only (Frame.parent_frame_id).
-- Phase C extends this to active Mounts whose Placement.parent_frame
-- points at the referenced Frame.
--
-- The decommission_frame slice's longhand handler loads
-- `load_active_frame_consumers(frame_id)` from this projection
-- BEFORE calling the pure decider; the decider raises
-- FrameInUseError if any consumers exist.
--
-- Subscribed events (see apps/api/src/cora/equipment/projections/
-- frame_consumers.py):
--   - FrameRegistered     -> INSERT (referenced=parent_frame_id,
--                            consumer=this_frame_id, type='Frame')
--                            when parent_frame_id IS NOT NULL
--   - FrameDecommissioned -> DELETE WHERE consumer_id = this_frame_id
--                            (a Frame stops being a consumer of its
--                            parent once it is decommissioned)
--
-- Phase C will subscribe Mount lifecycle events to populate
-- consumer_type='Mount' rows.
--
-- ## Indexes
--
-- Primary key on (referenced_frame_id, consumer_id, consumer_type)
-- supports the dominant query ("any consumers referencing X?") via
-- prefix scan. Secondary index on consumer_id supports the
-- DELETE-by-consumer path when a child Frame (or Mount) goes away.

CREATE TABLE proj_equipment_frame_consumers (
    referenced_frame_id  UUID        NOT NULL,
    consumer_id          UUID        NOT NULL,
    consumer_type        TEXT        NOT NULL
                                     CHECK (consumer_type IN ('Frame', 'Mount')),
    registered_at        TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (referenced_frame_id, consumer_id, consumer_type)
);

CREATE INDEX proj_equipment_frame_consumers_by_consumer_idx
    ON proj_equipment_frame_consumers (consumer_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_equipment_frame_consumers TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_equipment_frame_consumers')
ON CONFLICT DO NOTHING;
