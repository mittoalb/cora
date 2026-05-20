-- Phase audit-2026-05-20 Iter B-4: surface Recipe.Capability lifecycle
-- timestamps on the projection (Path C replication, mirrors Iter A on
-- Method — see infra/atlas/migrations/20260520000000_add_method_summary_lifecycle_timestamps.sql).
--
-- Path C lock: state stays decider-minimal; lifecycle timestamps live
-- on the projection. `created_at` already lives on the row (set from
-- RecipeCapabilityDefined.occurred_at in the genesis INSERT).
--
--   - versioned_at  : null until RecipeCapabilityVersioned fires; set
--                     from event payload's occurred_at; updated on each
--                     re-version.
--   - deprecated_at : null until RecipeCapabilityDeprecated fires; set
--                     from event payload's occurred_at; terminal. Sits
--                     alongside the existing `replaced_by_capability_id`
--                     successor pointer (DLM-B catalog governance) —
--                     deprecated_at is "when" and replaced_by is "to
--                     what"; both populate on the same Deprecated event
--                     when a successor is named.
--
-- Both NULL-DEFAULT — existing rows backfill cleanly without
-- projection rebuild.

ALTER TABLE proj_recipe_capability_summary
    ADD COLUMN versioned_at  TIMESTAMPTZ,
    ADD COLUMN deprecated_at TIMESTAMPTZ;
