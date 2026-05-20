-- Phase audit-2026-05-20 Iter B-3: surface Family lifecycle timestamps
-- on the projection (Path C replication, mirrors Iter A on Method —
-- see infra/atlas/migrations/20260520000000_add_method_summary_lifecycle_timestamps.sql).
--
-- Path C lock: state stays decider-minimal; lifecycle timestamps live
-- on the projection. `created_at` already lives on the row (set from
-- (Family|Capability)Defined.occurred_at in the genesis INSERT).
--
--   - versioned_at  : null until (Family|Capability)Versioned fires;
--                     set from event payload's occurred_at; updated on
--                     each re-version.
--   - deprecated_at : null until (Family|Capability)Deprecated fires;
--                     set from event payload's occurred_at; terminal.
--
-- Both NULL-DEFAULT — existing rows backfill cleanly without
-- projection rebuild. Same dual-match (new + legacy) wiring as the
-- rest of FamilySummaryProjection per the post-5i Capability→Family
-- rename anti-hooks.

ALTER TABLE proj_equipment_family_summary
    ADD COLUMN versioned_at  TIMESTAMPTZ,
    ADD COLUMN deprecated_at TIMESTAMPTZ;
