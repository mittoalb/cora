-- Equipment BC's Fixture aggregate summary projection.
--
-- A Fixture is one materialization of an Assembly blueprint: the
-- recorded binding of pre-existing Assets to the Assembly's slots,
-- with parameter overrides + audit trail. The aggregate lives on
-- its own stream (one stream per fixture_id) and emits a single
-- genesis event (FixtureRegistered) per the Visit-instance pattern.
--
-- Folds the Fixture aggregate's single genesis event into a
-- queryable read model. Used by the future `list_fixtures` /
-- `get_fixture` slices and by Method.needed_assemblies satisfaction
-- queries that need to find Fixtures of an Assembly within a given
-- Surface.
--
-- Subscribed events (v1):
--   - FixtureRegistered -> INSERT (snapshot of assembly_content_hash,
--                          slot count + override count for cheap
--                          summary reads; full bindings live in the
--                          event payload).
--
-- The full `slot_asset_bindings` is intentionally NOT denormalized
-- here; the v1 read model carries summary counts only. A future
-- secondary projection table (proj_equipment_fixture_binding) lands
-- when a slot-resolution query trigger fires.
--
-- `assembly_content_hash` is indexed so federation / dedup queries
-- can locate every Fixture that carries a given structural
-- fingerprint across Surfaces. The composite (created_at,
-- fixture_id) index supports keyset pagination on the list
-- endpoint. The (surface_id, assembly_id) index supports the
-- "Fixtures of Assembly X within Surface Y" query that
-- Method.needed_assemblies satisfaction will use.
--
-- Mutable read model. cora_app gets full DML.
-- proj_equipment_fixture_summary matches:
--   - the table name (here)
--   - the bookmark row (INSERT below)
--   - `FixtureSummaryProjection.name` in
--     cora.equipment.projections.fixture_summary.

CREATE TABLE proj_equipment_fixture_summary (
    fixture_id              UUID        PRIMARY KEY,
    assembly_id             UUID        NOT NULL,
    assembly_content_hash   TEXT        NOT NULL,
    surface_id              UUID        NOT NULL,
    binding_count           INTEGER     NOT NULL,
    override_count          INTEGER     NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_equipment_fixture_summary_keyset_idx
    ON proj_equipment_fixture_summary (created_at, fixture_id);

-- Federation / dedup query support: find every Fixture that carries
-- this content_hash.
CREATE INDEX proj_equipment_fixture_summary_content_hash_idx
    ON proj_equipment_fixture_summary (assembly_content_hash);

-- Surface + Assembly composite: supports
-- "Fixtures of Assembly X within Surface Y" which the future
-- Method.needed_assemblies satisfaction query uses.
CREATE INDEX proj_equipment_fixture_summary_surface_assembly_idx
    ON proj_equipment_fixture_summary (surface_id, assembly_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_equipment_fixture_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_equipment_fixture_summary')
ON CONFLICT DO NOTHING;
