-- Session 5 Slice 7A: cross-deployment convergent Facility binding on Supply.
--
-- Adds the `facility_code` column to `proj_supply_summary` so the
-- Supply BC's read model carries the cross-deployment convergent slug
-- of the owning Facility (Federation BC's two-tier identity). The
-- `register_supply` slice's projection writer (apps/api/src/cora/supply/
-- projections/supply.py) populates this column on every
-- `SupplyRegistered` event going forward.
--
-- The column is nullable in this slice to keep the migration additive
-- per [[project_forward_only_migrations]]. The Supply projection
-- writer enforces non-null at write time (every SupplyRegistered
-- payload carries `facility_code`); Slice 7C will tighten the column
-- to NOT NULL alongside the UNIQUE INDEX migration that composes
-- `facility_code` into the (kind, name) uniqueness tuple. Forward-
-- only: no DROP, no rollback. A future compensating migration would
-- re-add the column if Slice 7 ever needed reversal.

ALTER TABLE proj_supply_summary
    ADD COLUMN facility_code TEXT NULL;
