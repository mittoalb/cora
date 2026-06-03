-- Adds Asset.fixture_id back-reference column to the Asset summary
-- projection so the conformance projection can answer "what Fixture
-- is this Asset bound into?" in O(1) without scanning Fixtures.
--
-- The column is set by the attach_asset_to_fixture slice (B.5):
-- AssetAttachedToFixture event fires on the Asset stream and the
-- projector writes the back-reference here. Default NULL until the
-- slice fires (additive, forward-only).
--
-- An index on fixture_id supports the reverse-lookup query
-- "list every Asset currently attached to Fixture X" that drives
-- the future conformance projection and the future
-- list_fixture_assets read slice.
--
-- Forward-only per project_forward_only_migrations: no DROP.

ALTER TABLE proj_equipment_asset_summary
    ADD COLUMN fixture_id UUID NULL;

CREATE INDEX proj_equipment_asset_summary_fixture_id_idx
    ON proj_equipment_asset_summary (fixture_id)
    WHERE fixture_id IS NOT NULL;
