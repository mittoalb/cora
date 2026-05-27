-- Add asset<->family join projection.
--
-- The AssetSummaryProjection's module docstring (`apps/api/src/cora/
-- equipment/projections/asset.py`) explicitly defers this projection
-- ("Belong in a future `proj_equipment_asset_capabilities` projection
-- (deferred until a list-by-family query demands it)"). The
-- inspect_plan_binding diagnostic's future enumeration of "other
-- Assets in the facility that afford X" is that consumer.
--
-- ## Shape
--
-- Skinny (asset_id, family_id, added_at). The aggregate state already
-- owns the canonical set (Asset.families); this projection mirrors
-- the membership relation for query convenience. `added_at` records
-- when the association was projected; useful for ordering recent
-- changes in operator UIs.
--
-- ## Indexes
--
-- Primary key (asset_id, family_id) supports "Families for Asset"
-- (the dominant per-Asset read in the diagnostic).
-- Reverse index (family_id, asset_id) supports "Assets carrying
-- Family X" -- the next phase's "list candidate Assets affording
-- requirement Y" join target.
--
-- ## Idempotency
--
-- INSERT uses ON CONFLICT DO NOTHING to tolerate re-application
-- on projection replay; DELETE is naturally idempotent. The
-- aggregate's strict-not-idempotent guards run at command time;
-- this projection is replay-safe regardless.

CREATE TABLE proj_equipment_asset_families (
    asset_id  UUID        NOT NULL,
    family_id UUID        NOT NULL,
    added_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (asset_id, family_id)
);

CREATE INDEX proj_equipment_asset_families_by_family_idx
    ON proj_equipment_asset_families (family_id, asset_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_equipment_asset_families TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_equipment_asset_families')
ON CONFLICT DO NOTHING;
