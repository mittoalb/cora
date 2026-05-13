-- Phase 8e-7 post-merge cleanup: missing partial index on
-- proj_decision_summary.confidence_band.
--
-- Gate-review surfaced that the original Phase 8e-7 migration
-- (20260513020000_init_proj_decision_summary.sql) declared indexes
-- for actor_id and decision_rule but skipped confidence_band, even
-- though the list_decisions handler filters on it
-- (`WHERE ($2::text IS NULL OR confidence_band = $2)`). With
-- Low/Medium/High/Certain cardinality of 4 over a potentially
-- large Decision stream the planner would full-scan filtered
-- queries; this index makes it a fast indexed lookup.
--
-- Partial WHERE matches the established rule (other nullable
-- filter columns use partial indexes; see Data BC's run_idx /
-- subject_idx in 20260513010000).
--
-- Forward-only per project_forward_only_migrations memory: rather
-- than amend the original migration, ship the fix as a separate
-- forward migration (the original was already committed; immutable
-- by policy even if not yet deployed).

CREATE INDEX proj_decision_summary_band_idx
    ON proj_decision_summary (confidence_band)
    WHERE confidence_band IS NOT NULL;
