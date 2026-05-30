-- Init proj_equipment_frame_summary: read model for the Frame aggregate.
--
-- Subscribed events (see apps/api/src/cora/equipment/projections/
-- frame_summary.py):
--   - FrameRegistered     -> INSERT (status=Active; name, parent_frame_id,
--                            placement_relative_to_parent from payload)
--   - FrameUpdated        -> UPDATE placement_relative_to_parent
--   - FrameDecommissioned -> UPDATE status=Decommissioned
--
-- ## Shape
--
-- One row per Frame. `parent_frame_id` is nullable (root frames have
-- no parent). `placement_relative_to_parent` is JSONB to carry the
-- full 15-field Placement VO payload; null for root frames.
--
-- ## Indexes
--
-- Primary key on frame_id (the dominant per-Frame read). Secondary
-- index on parent_frame_id supports tree walks ("list children of
-- this frame"); status filters the active subset.
--
-- ## Idempotency
--
-- INSERT uses ON CONFLICT DO NOTHING; UPDATEs write fixed values
-- per event type for replay safety. Mirrors AssetSummaryProjection.

CREATE TABLE proj_equipment_frame_summary (
    frame_id                        UUID        PRIMARY KEY,
    name                            TEXT        NOT NULL,
    parent_frame_id                 UUID        NULL,
    placement_relative_to_parent    JSONB       NULL,
    status                          TEXT        NOT NULL
                                                CHECK (status IN ('Active', 'Decommissioned')),
    created_at                      TIMESTAMPTZ NOT NULL,
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_equipment_frame_summary_parent_idx
    ON proj_equipment_frame_summary (parent_frame_id)
    WHERE parent_frame_id IS NOT NULL;

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_equipment_frame_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_equipment_frame_summary')
ON CONFLICT DO NOTHING;
