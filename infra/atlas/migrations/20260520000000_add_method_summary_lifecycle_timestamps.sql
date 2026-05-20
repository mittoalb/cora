-- Phase audit-2026-05-20 Iter A: surface Method lifecycle timestamps on
-- the projection (Path C pilot).
--
-- The aggregate state stays minimal (decider purity per
-- Chassaing/Pellegrini/Reynhout): Method has `status` (Defined /
-- Versioned / Deprecated) but no `versioned_at` / `deprecated_at`
-- fields. The projection is the right home for derivable timestamps
-- (Dudycz "pragmatic redundancy" exception for read-side convenience;
-- K8s ObjectMeta / GitHub / AIP-142 precedent for materializing on the
-- resource representation).
--
-- `created_at` already lives on the row (set from MethodDefined.occurred_at
-- in the genesis INSERT). This migration adds the two missing lifecycle
-- transitions:
--   - versioned_at  : null until MethodVersioned fires; set from event
--                     payload's occurred_at; updated on each re-version
--                     (state always holds latest tag — same semantics).
--   - deprecated_at : null until MethodDeprecated fires; set from event
--                     payload's occurred_at; terminal.
--
-- Both NULL-DEFAULT — existing rows backfill cleanly without
-- projection rebuild. Future versioned/deprecated events update the
-- columns from the per-event occurred_at payload field.
--
-- Mirrored by Iter B for Plan/Practice/Family/Capability and by Iter
-- C/D for Agent/Surface (state-side timestamps removed in favor of
-- projection-side once their projections are aligned). See
-- memory/project_template_aggregate_timestamps.md.

ALTER TABLE proj_recipe_method_summary
    ADD COLUMN versioned_at  TIMESTAMPTZ,
    ADD COLUMN deprecated_at TIMESTAMPTZ;
