-- Phase audit-2026-05-20 Iter B-1: surface Plan lifecycle timestamps on
-- the projection (Path C replication, mirrors Iter A on Method —
-- see infra/atlas/migrations/20260520000000_add_method_summary_lifecycle_timestamps.sql).
--
-- State stays minimal per decider purity (Chassaing/Pellegrini/
-- Reynhout); lifecycle timestamps live on the projection per Dudycz
-- read-side-pragmatism + K8s ObjectMeta / GitHub / AIP-142 resource-
-- API precedent. `created_at` already lives on the row (set from
-- PlanDefined.occurred_at in the genesis INSERT).
--
--   - versioned_at  : null until PlanVersioned fires; set from event
--                     payload's occurred_at; updated on each re-version
--                     (projection mirrors state's always-holds-latest
--                     convention).
--   - deprecated_at : null until PlanDeprecated fires; set from event
--                     payload's occurred_at; terminal.
--
-- Both NULL-DEFAULT — existing rows backfill cleanly without
-- projection rebuild.

ALTER TABLE proj_recipe_plan_summary
    ADD COLUMN versioned_at  TIMESTAMPTZ,
    ADD COLUMN deprecated_at TIMESTAMPTZ;
