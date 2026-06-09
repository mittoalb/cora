-- Post-Slice-7 SupplyScope retirement cleanup: drop the decorative
-- `scope` column + CHECK constraint from `proj_supply_summary`.
--
-- Slice 7C swapped the UNIQUE INDEX expression from
-- `(scope, kind, name)` to
-- `(facility_code, COALESCE(containing_asset_id::text, ''), kind, name)`,
-- which left `proj_supply_summary.scope` decorative: still populated by
-- the projection writer + still surfaced by `SELECT` queries, but no
-- longer load-bearing for cross-stream uniqueness. Slice 7D retired
-- the `?scope=` filter on the `list_supplies` endpoint. This migration
-- closes the loop by dropping the column and its CHECK constraint
-- entirely, in lockstep with the application-tier removal of:
--
--   - the `SupplyScope` StrEnum (`cora.supply.aggregates.supply.state`)
--   - the `Supply.scope` aggregate-state field
--   - the `SupplyRegistered.scope` event-payload key + to_payload /
--     from_stored arms
--   - the `register_supply` REST body + MCP tool `scope` parameter
--   - the `SupplyReference.scope` cross-BC port field
--
-- The address tuple `(facility_code, containing_asset_id, kind, name)`
-- is the canonical structural shape going forward; structural roles
-- formerly carried by `SupplyScope.Sector` / `SupplyScope.Beamline`
-- are modeled relationally as Equipment BC Asset references per
-- [[project_supply_sector_disposition]] Option A.
--
-- Forward-only per [[project_forward_only_migrations]]. Pre-pilot
-- greenfield: no consumers query the `scope` column, no downstream
-- replicas exist; the DROP is safe with zero coordination. ALTER
-- TABLE DROP COLUMN and DROP CONSTRAINT are both fast at PG's table-
-- level lock granularity.

ALTER TABLE proj_supply_summary
    DROP CONSTRAINT IF EXISTS proj_supply_summary_scope_check;

ALTER TABLE proj_supply_summary
    DROP COLUMN scope;
