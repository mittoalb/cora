-- Phase 5g-b: track Asset.condition (Nominal / Degraded / Faulted)
-- on the Asset summary projection, orthogonal to the existing
-- lifecycle column.
--
-- Adds a single TEXT column `condition` to
-- `proj_equipment_asset_summary`. Defaults to 'Nominal'; existing
-- rows backfill cleanly with the default (the only condition any
-- pre-5g-b Asset has ever held, since condition transitions didn't
-- exist before this phase).
--
-- ## Why a TEXT column, not an enum
--
-- Matches the precedent set by `lifecycle TEXT` (same projection)
-- and `status TEXT` across the other BCs' summary projections.
-- Postgres enums are not portable across migrations (rename / value
-- removal is awkward); CHECK constraints inline to the table give
-- the same safety with cleaner evolution. Keeps the migration
-- shape consistent with sibling tables.
--
-- ## Default semantics
--
-- 'Nominal' for both pre-5g-b Assets (no condition event ever
-- emitted) AND for newly-registered Assets (default-via-state at the
-- aggregate level matches default-via-DEFAULT here). Becomes
-- 'Degraded' / 'Faulted' on the corresponding event; goes back to
-- 'Nominal' on AssetRestored.
--
-- ## CHECK constraint
--
-- Pins the three valid values at the DB level, mirrors how
-- `Run.status` is constrained in `proj_run_summary`. Future enum
-- additions require a migration that drops + re-adds the CHECK with
-- the wider set, same pattern as elsewhere.
--
-- Pure ADD COLUMN with safe default; greenfield-friendly.

ALTER TABLE proj_equipment_asset_summary
    ADD COLUMN condition TEXT NOT NULL DEFAULT 'Nominal'
        CHECK (condition IN ('Nominal', 'Degraded', 'Faulted'));
